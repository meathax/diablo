// SPDX-License-Identifier: GPL-2.0-or-later
// Bounded FPGA consumer for the ARM command stream.
//
// The consumer executes FillRect rows as aligned 64-bit byte-enable writes and
// groups up to eight full words into one bounded DDR burst. CopyRect remains
// byte-granular because overlap-safe reads and writes need the source byte
// value, while constant-color fills can safely use every lane in a DDR word.
// This keeps command execution bounded without changing ownership or clipping
// semantics, and leaves short unaligned edges as single-word transactions.
module diablo_command_consumer #(
    parameter integer POLL_INTERVAL_CYCLES = 50400
) (
    input wire clk,
    input wire reset,
    input wire session_valid,
    input wire [31:0] session_epoch,
    input wire [31:0] target_pixel_base,

    input wire ddram_busy,
    input wire [63:0] ddram_dout,
    input wire ddram_dout_ready,
    output wire [7:0] ddram_burstcnt,
    output wire [28:0] ddram_addr,
    output wire ddram_rd,
    output wire [63:0] ddram_din,
    output wire [7:0] ddram_be,
    output wire ddram_we,

    output reg ring_valid = 1'b0,
    output reg fault = 1'b0,
    output reg [31:0] commands_executed = 0,
    output reg [31:0] commands_rejected = 0,
    output reg [63:0] last_fence = 0
);
    `include "diablo_transport_abi.svh"

    localparam [28:0] SHARED_BASE_WORD = 29'h07fc0000;
    localparam [28:0] RECORD_CONTROL_WORD = SHARED_BASE_WORD + 29'd14;
    localparam [28:0] RECORD_LAYOUT_WORD = SHARED_BASE_WORD + 29'd15;
    localparam [28:0] RECORD_EPOCH_WORD = SHARED_BASE_WORD + 29'd17;
    localparam [28:0] PAYLOAD_CONTROL_WORD = SHARED_BASE_WORD + 29'd18;
    localparam [28:0] PAYLOAD_LAYOUT_WORD = SHARED_BASE_WORD + 29'd19;
    localparam [28:0] PAYLOAD_EPOCH_WORD = SHARED_BASE_WORD + 29'd21;
    localparam [28:0] RECORD_DATA_BASE_WORD = SHARED_BASE_WORD
                                             + (DIABLO_TRANSPORT_COMMAND_RECORDS_OFFSET >> 3);
    localparam [28:0] PAYLOAD_DATA_BASE_WORD = SHARED_BASE_WORD
                                             + (DIABLO_TRANSPORT_COMMAND_PAYLOAD_OFFSET >> 3);
    localparam [28:0] LAST_COMPLETED_FENCE_WORD = SHARED_BASE_WORD + 29'd47;
    // A zero interval is a valid stress-test setting and must poll every
    // cycle, rather than underflowing the comparison to a long 16-bit delay.
    localparam integer POLL_INTERVAL_LIMIT =
        (POLL_INTERVAL_CYCLES <= 0) ? 1 : POLL_INTERVAL_CYCLES;

    localparam [4:0] INACTIVE = 5'd0;
    localparam [4:0] VERIFY_REQUEST = 5'd1;
    localparam [4:0] VERIFY_WAIT = 5'd2;
    localparam [4:0] POLL_RECORD_REQUEST = 5'd3;
    localparam [4:0] POLL_RECORD_WAIT = 5'd4;
    localparam [4:0] POLL_PAYLOAD_REQUEST = 5'd5;
    localparam [4:0] POLL_PAYLOAD_WAIT = 5'd6;
    localparam [4:0] RECORD_REQUEST = 5'd7;
    localparam [4:0] RECORD_WAIT = 5'd8;
    localparam [4:0] DISPATCH = 5'd9;
    localparam [4:0] FILL_WRITE = 5'd10;
    localparam [4:0] COPY_READ_REQUEST = 5'd11;
    localparam [4:0] COPY_READ_WAIT = 5'd12;
    localparam [4:0] COPY_WRITE = 5'd13;
    localparam [4:0] ACK_RECORD = 5'd14;
    localparam [4:0] ACK_PAYLOAD = 5'd15;
    localparam [4:0] WRITE_FENCE = 5'd16;
    localparam [4:0] REVERIFY_WAIT = 5'd17;
    localparam [4:0] FILL_SETUP = 5'd18;
    localparam [4:0] COPY_SETUP = 5'd19;
    localparam [4:0] FILL_ARM = 5'd20;
    localparam [4:0] COPY_ARM = 5'd21;

    localparam [31:0] OPCODE_FILL = 32'd1;
    localparam [31:0] OPCODE_COPY = 32'd2;
    localparam [31:0] OPCODE_END = 32'h0000ffff;

    reg [4:0] state = INACTIVE;
    reg [2:0] verify_index = 0;
    reg verify_ok = 1'b0;
    reg [31:0] active_epoch = 0;
    reg [31:0] record_producer = 0;
    reg [31:0] record_consumer = 0;
    reg [31:0] payload_producer = 0;
    reg [31:0] payload_consumer = 0;
    reg [31:0] poll_counter = 0;

    reg [1:0] record_word_index = 0;
    reg [31:0] record_opcode = 0;
    reg [31:0] record_flags = 0;
    reg signed [31:0] record_x = 0;
    reg signed [31:0] record_y = 0;
    reg signed [31:0] record_width = 0;
    reg signed [31:0] record_height = 0;
    reg [31:0] record_payload_offset = 0;
    reg [31:0] record_payload_bytes = 0;
    reg record_is_end = 1'b0;
    reg [63:0] record_fence = 0;

    reg [31:0] render_x = 0;
    reg [31:0] render_y = 0;
    reg [31:0] render_width = 0;
    reg [31:0] render_height = 0;
    reg [31:0] render_column = 0;
    reg [31:0] render_row = 0;
    reg [7:0] render_color = 0;
    reg [3:0] fill_burst_length = 1;
    reg [3:0] fill_burst_remaining = 1;
    reg [31:0] fill_burst_byte_offset = 0;
    reg [7:0] fill_burst_mask = 8'h01;
    reg [1:0] target_slot = 0;
    reg signed [31:0] source_x = 0;
    reg signed [31:0] source_y = 0;
    reg copy_reverse_x = 1'b0;
    reg copy_reverse_y = 1'b0;
    reg [7:0] copy_byte = 0;

    // Blocking temporaries used only while clipping one command at DISPATCH.
    // Command coordinates are signed 32-bit values, so do clipping in a wider
    // signed representation. This rejects malformed INT_MIN/INT_MAX records
    // safely instead of relying on wraparound in negation or extent addition.
    reg signed [63:0] temp_dest_x;
    reg signed [63:0] temp_dest_y;
    reg signed [63:0] temp_source_x;
    reg signed [63:0] temp_source_y;
    reg signed [63:0] temp_width;
    reg signed [63:0] temp_height;
    reg signed [63:0] temp_left;
    reg signed [63:0] temp_top;
    reg signed [63:0] temp_right;
    reg signed [63:0] temp_bottom;
    localparam signed [63:0] FRAME_WIDTH_SIGNED = DIABLO_TRANSPORT_FRAME_WIDTH;
    localparam signed [63:0] FRAME_HEIGHT_SIGNED = DIABLO_TRANSPORT_FRAME_HEIGHT;

    wire [31:0] record_occupied = record_producer - record_consumer;
    wire [31:0] payload_occupied = payload_producer - payload_consumer;
    wire record_overflow = record_occupied > DIABLO_TRANSPORT_COMMAND_RECORDS_CAPACITY;
    wire payload_overflow = payload_occupied > DIABLO_TRANSPORT_COMMAND_PAYLOAD_CAPACITY;

    wire [31:0] fill_pixel_x = render_x + render_column;
    wire [31:0] fill_pixel_y = render_y + render_row;
    wire [31:0] copy_column = copy_reverse_x
                            ? (render_width - 1'b1 - render_column)
                            : render_column;
    wire [31:0] copy_row = copy_reverse_y
                         ? (render_height - 1'b1 - render_row)
                         : render_row;
    wire [31:0] copy_destination_x = render_x + copy_column;
    wire [31:0] copy_destination_y = render_y + copy_row;
    wire [31:0] copy_source_pixel_x = source_x + copy_column;
    wire [31:0] copy_source_pixel_y = source_y + copy_row;
    wire [31:0] fill_byte_offset = fill_pixel_y * DIABLO_TRANSPORT_FRAME_WIDTH + fill_pixel_x;
    wire [31:0] fill_remaining = render_width - render_column;
    // A clipped row is at most 640 pixels, so seven bits cover all complete
    // words. Keeping this arithmetic narrow avoids a wide compare on the
    // timing-sensitive DDR request path.
    wire [6:0] fill_full_words = fill_remaining[9:3];
    wire [3:0] fill_burst_words = (fill_full_words > 7'd8)
                                ? 4'd8 : fill_full_words[3:0];
    wire [3:0] fill_chunk = (fill_remaining < (32'd8 - {29'd0, fill_byte_offset[2:0]}))
                          ? fill_remaining[3:0]
                          : (4'd8 - {1'b0, fill_byte_offset[2:0]});
    wire [7:0] fill_mask = (8'hff >> (4'd8 - fill_chunk)) << fill_byte_offset[2:0];
    wire [31:0] copy_destination_byte_offset = copy_destination_y * DIABLO_TRANSPORT_FRAME_WIDTH
                                             + copy_destination_x;
    wire [31:0] copy_source_byte_offset = copy_source_pixel_y * DIABLO_TRANSPORT_FRAME_WIDTH
                                        + copy_source_pixel_x;
    wire [31:0] selected_target_base = target_pixel_base
                                      + target_slot * DIABLO_TRANSPORT_FRAME_SLOT_BYTES;
    wire [28:0] target_base_word = selected_target_base[31:3];

    function automatic [28:0] record_address(input [31:0] seq_value, input [1:0] word_index);
        begin
            record_address = RECORD_DATA_BASE_WORD
                           + {16'd0, seq_value[10:0], 2'b00}
                           + {27'd0, word_index};
        end
    endfunction

    function automatic [28:0] pixel_address(input [28:0] base_word, input [31:0] byte_offset);
        begin
            // Pass the base explicitly.  Keeping it as a function argument
            // makes the combinational address update when a command selects a
            // different frame slot; a hidden module-level reference can leave
            // the first write using the previous slot in simulation/synthesis.
            pixel_address = base_word + byte_offset[31:3];
        end
    endfunction

    function automatic [63:0] shifted_byte(input [7:0] value, input [2:0] lane);
        begin
            shifted_byte = {56'd0, value} << (lane * 8);
        end
    endfunction

    function automatic [7:0] selected_byte(input [63:0] value, input [2:0] lane);
        begin
            selected_byte = (value >> (lane * 8)) & 8'hff;
        end
    endfunction

    assign ddram_burstcnt = (state == FILL_WRITE) ? {4'd0, fill_burst_length} : 8'd1;
    assign ddram_rd = (state == VERIFY_REQUEST) || (state == POLL_RECORD_REQUEST)
                    || (state == POLL_PAYLOAD_REQUEST) || (state == RECORD_REQUEST)
                    || (state == COPY_READ_REQUEST);
    assign ddram_we = (state == FILL_WRITE) || (state == COPY_WRITE)
                    || (state == ACK_RECORD) || (state == ACK_PAYLOAD)
                    || (state == WRITE_FENCE);
    assign ddram_addr = (state == VERIFY_REQUEST)
                      ? ((verify_index == 0) ? RECORD_CONTROL_WORD
                       : (verify_index == 1) ? RECORD_LAYOUT_WORD
                       : (verify_index == 2) ? RECORD_EPOCH_WORD
                       : (verify_index == 3) ? PAYLOAD_CONTROL_WORD
                       : (verify_index == 4) ? PAYLOAD_LAYOUT_WORD
                       : PAYLOAD_EPOCH_WORD)
                      : (state == POLL_RECORD_REQUEST || state == POLL_RECORD_WAIT)
                      ? RECORD_CONTROL_WORD
                      : (state == POLL_PAYLOAD_REQUEST || state == POLL_PAYLOAD_WAIT)
                      ? PAYLOAD_CONTROL_WORD
                      : (state == RECORD_REQUEST || state == RECORD_WAIT)
                      ? record_address(record_consumer, record_word_index)
                      : (state == COPY_READ_REQUEST || state == COPY_READ_WAIT)
                       ? pixel_address(target_base_word, copy_source_byte_offset)
                      : (state == FILL_WRITE)
                       ? pixel_address(target_base_word, fill_burst_byte_offset)
                       : (state == COPY_WRITE)
                       ? pixel_address(target_base_word, copy_destination_byte_offset)
                      : (state == ACK_RECORD)
                      ? RECORD_CONTROL_WORD
                      : (state == ACK_PAYLOAD)
                      ? PAYLOAD_CONTROL_WORD
                      : (state == WRITE_FENCE)
                      ? LAST_COMPLETED_FENCE_WORD
                      : RECORD_CONTROL_WORD;
    assign ddram_din = (state == FILL_WRITE)
                     ? {8{render_color}}
                     : (state == COPY_WRITE)
                     ? shifted_byte(copy_byte, copy_destination_byte_offset[2:0])
                     : (state == ACK_RECORD)
                     ? {record_consumer + 1'b1, 32'd0}
                     : (state == ACK_PAYLOAD)
                     ? {payload_consumer + record_payload_bytes, 32'd0}
                     : (state == WRITE_FENCE)
                     ? record_fence
                     : 64'd0;
    assign ddram_be = (state == FILL_WRITE)
                    ? fill_burst_mask
                    : (state == COPY_WRITE)
                    ? (8'h01 << copy_destination_byte_offset[2:0])
                    : (state == ACK_RECORD || state == ACK_PAYLOAD)
                    ? 8'hf0
                    : (state == WRITE_FENCE)
                    ? 8'hff
                    : 8'h00;

    always @(posedge clk) begin
        if (reset || !session_valid) begin
            state <= INACTIVE;
            verify_index <= 0;
            verify_ok <= 1'b0;
            active_epoch <= 0;
            record_producer <= 0;
            record_consumer <= 0;
            payload_producer <= 0;
            payload_consumer <= 0;
            poll_counter <= 0;
            record_word_index <= 0;
            record_opcode <= 0;
            record_flags <= 0;
            record_x <= 0;
            record_y <= 0;
            record_width <= 0;
            record_height <= 0;
            record_payload_offset <= 0;
            record_payload_bytes <= 0;
            record_is_end <= 1'b0;
            record_fence <= 0;
            render_x <= 0;
            render_y <= 0;
            render_width <= 0;
            render_height <= 0;
            render_column <= 0;
            render_row <= 0;
            render_color <= 0;
            fill_burst_length <= 1;
            fill_burst_remaining <= 1;
            target_slot <= 0;
            source_x <= 0;
            source_y <= 0;
            copy_reverse_x <= 1'b0;
            copy_reverse_y <= 1'b0;
            copy_byte <= 0;
            ring_valid <= 1'b0;
            fault <= 1'b0;
            commands_executed <= 0;
            commands_rejected <= 0;
            last_fence <= 0;
        end else if (active_epoch != session_epoch) begin
            state <= VERIFY_REQUEST;
            verify_index <= 0;
            verify_ok <= 1'b1;
            active_epoch <= session_epoch;
            record_producer <= 0;
            record_consumer <= 0;
            payload_producer <= 0;
            payload_consumer <= 0;
            poll_counter <= 0;
            ring_valid <= 1'b0;
            fault <= 1'b0;
        end else begin
            case (state)
                INACTIVE: begin
                    verify_index <= 0;
                    verify_ok <= 1'b1;
                    state <= VERIFY_REQUEST;
                end

                VERIFY_REQUEST: if (!ddram_busy) state <= VERIFY_WAIT;

                VERIFY_WAIT: if (ddram_dout_ready) begin
                    case (verify_index)
                        0: begin
                            record_consumer <= ddram_dout[63:32];
                            record_producer <= ddram_dout[31:0];
                            if (ddram_dout[63:32] > ddram_dout[31:0]) verify_ok <= 1'b0;
                        end
                        1: if (ddram_dout[31:0] != DIABLO_TRANSPORT_COMMAND_RECORDS_CAPACITY
                             || ddram_dout[63:32] != DIABLO_TRANSPORT_COMMAND_RECORD_BYTES)
                            verify_ok <= 1'b0;
                        2: if (ddram_dout[31:0] != active_epoch) verify_ok <= 1'b0;
                        3: begin
                            payload_consumer <= ddram_dout[63:32];
                            payload_producer <= ddram_dout[31:0];
                            if (ddram_dout[63:32] > ddram_dout[31:0]) verify_ok <= 1'b0;
                        end
                        4: if (ddram_dout[31:0] != DIABLO_TRANSPORT_COMMAND_PAYLOAD_CAPACITY
                             || ddram_dout[63:32] != DIABLO_TRANSPORT_COMMAND_PAYLOAD_RECORD_BYTES)
                            verify_ok <= 1'b0;
                        default: begin
                            if (ddram_dout[31:0] != active_epoch) verify_ok <= 1'b0;
                            if (verify_ok && ddram_dout[31:0] == active_epoch) begin
                                ring_valid <= 1'b1;
                                poll_counter <= 0;
                                state <= POLL_RECORD_REQUEST;
                            end else begin
                                ring_valid <= 1'b0;
                                state <= REVERIFY_WAIT;
                            end
                        end
                    endcase
                    if (verify_index != 5) begin
                        verify_index <= verify_index + 1'b1;
                        state <= VERIFY_REQUEST;
                    end
                end

                POLL_RECORD_REQUEST: if (!ddram_busy) state <= POLL_RECORD_WAIT;

                POLL_RECORD_WAIT: if (ddram_dout_ready) begin
                    record_producer <= ddram_dout[31:0];
                    if (ddram_dout[63:32] != record_consumer
                        || ddram_dout[31:0] - record_consumer > DIABLO_TRANSPORT_COMMAND_RECORDS_CAPACITY) begin
                        fault <= 1'b1;
                        ring_valid <= 1'b0;
                        state <= REVERIFY_WAIT;
                    end else begin
                        state <= POLL_PAYLOAD_REQUEST;
                    end
                end

                POLL_PAYLOAD_REQUEST: if (!ddram_busy) state <= POLL_PAYLOAD_WAIT;

                POLL_PAYLOAD_WAIT: if (ddram_dout_ready) begin
                    payload_producer <= ddram_dout[31:0];
                    if (ddram_dout[63:32] != payload_consumer
                        || ddram_dout[31:0] - payload_consumer > DIABLO_TRANSPORT_COMMAND_PAYLOAD_CAPACITY) begin
                        fault <= 1'b1;
                        ring_valid <= 1'b0;
                        state <= REVERIFY_WAIT;
                    end else if (record_producer != record_consumer) begin
                        record_word_index <= 0;
                        state <= RECORD_REQUEST;
                    end else if (poll_counter >= POLL_INTERVAL_LIMIT - 1) begin
                        poll_counter <= 0;
                        state <= POLL_RECORD_REQUEST;
                    end else begin
                        poll_counter <= poll_counter + 1'b1;
                        state <= POLL_RECORD_REQUEST;
                    end
                end

                RECORD_REQUEST: if (!ddram_busy) state <= RECORD_WAIT;

                RECORD_WAIT: if (ddram_dout_ready) begin
                    case (record_word_index)
                        0: begin
                            record_opcode <= ddram_dout[31:0];
                            record_flags <= ddram_dout[63:32];
                        end
                        1: begin
                            record_x <= $signed(ddram_dout[31:0]);
                            record_y <= $signed(ddram_dout[63:32]);
                        end
                        2: begin
                            record_width <= $signed(ddram_dout[31:0]);
                            record_height <= $signed(ddram_dout[63:32]);
                        end
                        default: begin
                            record_payload_offset <= ddram_dout[31:0];
                            record_payload_bytes <= ddram_dout[63:32];
                        end
                    endcase
                    if (record_word_index == 3) state <= DISPATCH;
                    else begin
                        record_word_index <= record_word_index + 1'b1;
                        state <= RECORD_REQUEST;
                    end
                end

                DISPATCH: begin
                    record_is_end <= 1'b0;
                    if (record_opcode == OPCODE_END) begin
                        record_is_end <= 1'b1;
                        record_fence <= {record_payload_offset, record_payload_bytes};
                        state <= ACK_RECORD;
                    end else if (record_opcode == OPCODE_FILL && record_payload_bytes == 0
                                 && record_flags[9:8] != 2'd3) begin
                        target_slot <= record_flags[9:8];
                        temp_dest_x = record_x;
                        temp_dest_y = record_y;
                        temp_width = record_width;
                        temp_height = record_height;
                        if (temp_dest_x < 0) begin temp_width = temp_width + temp_dest_x; temp_dest_x = 0; end
                        if (temp_dest_y < 0) begin temp_height = temp_height + temp_dest_y; temp_dest_y = 0; end
                        if (temp_dest_x + temp_width > FRAME_WIDTH_SIGNED)
                            temp_width = FRAME_WIDTH_SIGNED - temp_dest_x;
                        if (temp_dest_y + temp_height > FRAME_HEIGHT_SIGNED)
                            temp_height = FRAME_HEIGHT_SIGNED - temp_dest_y;
                        if (temp_width <= 0 || temp_height <= 0) begin
                            commands_rejected <= commands_rejected + 1'b1;
                            state <= ACK_RECORD;
                        end else begin
                            render_x <= temp_dest_x;
                            render_y <= temp_dest_y;
                            render_width <= temp_width;
                            render_height <= temp_height;
                            render_column <= 0;
                            render_row <= 0;
                            render_color <= record_flags[7:0];
                            fill_burst_length <= 1;
                            fill_burst_remaining <= 1;
                            fill_burst_byte_offset <= 0;
                            fill_burst_mask <= 8'h01;
                            state <= FILL_SETUP;
                        end
                    end else if (record_opcode == OPCODE_COPY && record_payload_bytes == 0
                                 && record_flags[9:8] != 2'd3) begin
                        target_slot <= record_flags[9:8];
                        temp_dest_x = record_x;
                        temp_dest_y = record_y;
                        temp_source_x = $signed(record_payload_offset[15:0]);
                        temp_source_y = $signed(record_payload_offset[31:16]);
                        temp_width = record_width;
                        temp_height = record_height;
                        temp_left = 0;
                        if (-temp_dest_x > temp_left) temp_left = -temp_dest_x;
                        if (-temp_source_x > temp_left) temp_left = -temp_source_x;
                        temp_top = 0;
                        if (-temp_dest_y > temp_top) temp_top = -temp_dest_y;
                        if (-temp_source_y > temp_top) temp_top = -temp_source_y;
                        temp_right = temp_width;
                        if (FRAME_WIDTH_SIGNED - temp_dest_x < temp_right)
                            temp_right = FRAME_WIDTH_SIGNED - temp_dest_x;
                        if (FRAME_WIDTH_SIGNED - temp_source_x < temp_right)
                            temp_right = FRAME_WIDTH_SIGNED - temp_source_x;
                        temp_bottom = temp_height;
                        if (FRAME_HEIGHT_SIGNED - temp_dest_y < temp_bottom)
                            temp_bottom = FRAME_HEIGHT_SIGNED - temp_dest_y;
                        if (FRAME_HEIGHT_SIGNED - temp_source_y < temp_bottom)
                            temp_bottom = FRAME_HEIGHT_SIGNED - temp_source_y;
                        temp_width = temp_right - temp_left;
                        temp_height = temp_bottom - temp_top;
                        if (temp_width <= 0 || temp_height <= 0) begin
                            commands_rejected <= commands_rejected + 1'b1;
                            state <= ACK_RECORD;
                        end else begin
                            render_x <= temp_dest_x + temp_left;
                            render_y <= temp_dest_y + temp_top;
                            source_x <= temp_source_x + temp_left;
                            source_y <= temp_source_y + temp_top;
                            render_width <= temp_width;
                            render_height <= temp_height;
                            render_column <= 0;
                            render_row <= 0;
                            copy_reverse_x <= (temp_dest_x + temp_left) > (temp_source_x + temp_left);
                            copy_reverse_y <= (temp_dest_y + temp_top) > (temp_source_y + temp_top);
                            state <= COPY_SETUP;
                        end
                    end else begin
                        commands_rejected <= commands_rejected + 1'b1;
                        state <= ACK_RECORD;
                    end
                end

                FILL_WRITE: if (!ddram_busy) begin
                    if (fill_burst_remaining > 1) begin
                        // A burst is issued only from an aligned pixel word and
                        // therefore every beat is a complete eight-byte fill.
                        fill_burst_remaining <= fill_burst_remaining - 1'b1;
                        render_column <= render_column + 32'd8;
                    end else if (render_column + fill_chunk >= render_width) begin
                        fill_burst_remaining <= 1;
                        render_column <= 0;
                        if (render_row + 1 >= render_height) state <= ACK_RECORD;
                        else begin
                            render_row <= render_row + 1'b1;
                            state <= FILL_SETUP;
                        end
                    end else begin
                        fill_burst_remaining <= 1;
                        render_column <= render_column + fill_chunk;
                        state <= FILL_SETUP;
                    end
                end

                // Keep the write strobe deasserted for two cycles after a
                // dispatch.  This gives the target-slot base arithmetic a
                // complete settling cycle before the first byte transaction.
                FILL_SETUP: state <= FILL_ARM;

                FILL_ARM: begin
                    // Keep edge words isolated so their byte enables may differ.
                    // Aligned interior words are grouped into at most eight beats
                    // to bound DDR occupancy and preserve audio/input priority.
                    fill_burst_byte_offset <= fill_byte_offset;
                    fill_burst_mask <= fill_mask;
                    if (fill_byte_offset[2:0] == 0 && fill_remaining >= 32'd8)
                        fill_burst_length <= fill_burst_words;
                    else
                        fill_burst_length <= 1;
                    fill_burst_remaining <= (fill_byte_offset[2:0] == 0 && fill_remaining >= 32'd8)
                                         ? fill_burst_words
                                         : 1;
                    state <= FILL_WRITE;
                end

                COPY_SETUP: state <= COPY_ARM;

                COPY_ARM: state <= COPY_READ_REQUEST;

                COPY_READ_REQUEST: if (!ddram_busy) state <= COPY_READ_WAIT;

                COPY_READ_WAIT: if (ddram_dout_ready) begin
                    copy_byte <= selected_byte(ddram_dout, copy_source_byte_offset[2:0]);
                    state <= COPY_WRITE;
                end

                COPY_WRITE: if (!ddram_busy) begin
                    if (render_column + 1 >= render_width) begin
                        render_column <= 0;
                        if (render_row + 1 >= render_height) state <= ACK_RECORD;
                        else begin
                            render_row <= render_row + 1'b1;
                            state <= COPY_READ_REQUEST;
                        end
                    end else begin
                        render_column <= render_column + 1'b1;
                        state <= COPY_READ_REQUEST;
                    end
                end

                ACK_RECORD: if (!ddram_busy) begin
                    record_consumer <= record_consumer + 1'b1;
                    commands_executed <= commands_executed + 1'b1;
                    if (record_is_end) state <= WRITE_FENCE;
                    else if (record_payload_bytes != 0) state <= ACK_PAYLOAD;
                    else state <= POLL_RECORD_REQUEST;
                end

                ACK_PAYLOAD: if (!ddram_busy) begin
                    payload_consumer <= payload_consumer + record_payload_bytes;
                    state <= POLL_RECORD_REQUEST;
                end

                WRITE_FENCE: if (!ddram_busy) begin
                    last_fence <= record_fence;
                    state <= POLL_RECORD_REQUEST;
                end

                REVERIFY_WAIT: begin
                    if (poll_counter >= POLL_INTERVAL_LIMIT - 1) begin
                        poll_counter <= 0;
                        verify_index <= 0;
                        verify_ok <= 1'b1;
                        state <= VERIFY_REQUEST;
                    end else poll_counter <= poll_counter + 1'b1;
                end

                default: state <= INACTIVE;
            endcase
        end
    end
endmodule
