// SPDX-License-Identifier: GPL-2.0-or-later
// Capture MiSTer HPS input edges into the ARM-consumed input ring.
//
// The FPGA is the producer.  Each event is four 64-bit writes (32 bytes),
// followed by a low-half producer publication in the ring control word.  The
// ARM owns the high-half consumer cursor, so an ARM poll can reclaim space
// without racing an event write.
module diablo_input_capture #(
    parameter integer POLL_INTERVAL_CYCLES = 50400
) (
    input wire clk,
    input wire reset,
    input wire session_valid,
    input wire [31:0] session_epoch,

    input wire [31:0] joystick_0,
    input wire [15:0] joystick_l_analog_0,
    input wire [15:0] joystick_r_analog_0,
    input wire [10:0] ps2_key,
    input wire [24:0] ps2_mouse,
    input wire [15:0] ps2_mouse_ext,
    input wire [1:0] buttons,
    // High while MiSTer's OSD owns interaction. This is the focus boundary
    // exposed to the ARM application; physical button state remains payload.
    input wire osd_status,

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
    output reg [31:0] overflow_count = 0
);
    `include "diablo_transport_abi.svh"

    localparam [28:0] SHARED_BASE_WORD = 29'h07fc0000;
    localparam [28:0] INPUT_CONTROL_WORD = SHARED_BASE_WORD + 29'd6;
    localparam [28:0] INPUT_LAYOUT_WORD = SHARED_BASE_WORD + 29'd7;
    localparam [28:0] INPUT_DROPPED_WORD = SHARED_BASE_WORD + 29'd8;
    localparam [28:0] INPUT_EPOCH_WORD = SHARED_BASE_WORD + 29'd9;
    localparam [28:0] INPUT_DATA_BASE_WORD = SHARED_BASE_WORD
                                           + (DIABLO_TRANSPORT_INPUT_REGION_OFFSET >> 3);
    // Treat a zero poll interval as one cycle instead of allowing the
    // comparison below to underflow to 16'hffff and silently disable polling.
    localparam integer POLL_INTERVAL_LIMIT =
        (POLL_INTERVAL_CYCLES <= 0) ? 1 : POLL_INTERVAL_CYCLES;

    localparam [3:0] INACTIVE = 4'd0;
    localparam [3:0] VERIFY_REQUEST = 4'd1;
    localparam [3:0] VERIFY_WAIT = 4'd2;
    localparam [3:0] IDLE = 4'd3;
    localparam [3:0] WRITE_EVENT = 4'd4;
    localparam [3:0] PUBLISH_PRODUCER = 4'd5;
    localparam [3:0] POLL_REQUEST = 4'd6;
    localparam [3:0] POLL_WAIT = 4'd7;
    localparam [3:0] REVERIFY_WAIT = 4'd8;
    localparam [3:0] PUBLISH_DROPPED = 4'd9;

    reg [3:0] state = INACTIVE;
    reg [1:0] verify_index = 0;
    reg layout_valid = 1'b0;
    reg verified_once = 1'b0;
    reg [31:0] active_epoch = 0;
    reg [31:0] producer_sequence = 0;
    reg [31:0] consumer_sequence = 0;
    reg [31:0] timestamp_counter = 0;
    reg [15:0] poll_counter = 0;

    reg last_key_toggle = 1'b0;
    reg last_mouse_toggle = 1'b0;
    reg [31:0] last_joystick = 0;
    reg [15:0] last_left_analog = 0;
    reg [15:0] last_right_analog = 0;
    reg last_osd_status = 1'b0;

    reg [31:0] event_sequence = 0;
    reg [31:0] event_timestamp = 0;
    reg [31:0] event_type = 0;
    reg [31:0] event_code = 0;
    reg [31:0] event_value0 = 0;
    reg [31:0] event_value1 = 0;
    reg [63:0] event_buttons = 0;
    reg [1:0] write_index = 0;
    reg [63:0] dropped_count = 0;

    wire [31:0] occupied = producer_sequence - consumer_sequence;
    wire ring_full = occupied >= DIABLO_TRANSPORT_INPUT_CAPACITY;
    wire key_changed = ps2_key[10] != last_key_toggle;
    wire mouse_changed = ps2_mouse[24] != last_mouse_toggle;
    wire joystick_changed = (joystick_0 != last_joystick)
                         || (joystick_l_analog_0 != last_left_analog)
                         || (joystick_r_analog_0 != last_right_analog);
    wire focus_changed = osd_status != last_osd_status;
    wire input_changed = key_changed || mouse_changed || joystick_changed || focus_changed;

    wire [31:0] keyboard_code = {23'd0, ps2_key[8], ps2_key[7:0]};
    wire [31:0] mouse_code = {21'd0, ps2_mouse[2:0], ps2_mouse_ext[7:0]};
    wire [31:0] mouse_dx = {{24{ps2_mouse[15]}}, ps2_mouse[15:8]};
    wire [31:0] mouse_dy = {{24{ps2_mouse[23]}}, ps2_mouse[23:16]};
    wire [31:0] left_analog = {{16{joystick_l_analog_0[15]}}, joystick_l_analog_0};
    wire [31:0] right_analog = {{16{joystick_r_analog_0[15]}}, joystick_r_analog_0};
    wire [63:0] current_buttons = {30'd0, buttons, joystick_0};

    function automatic [28:0] input_data_address(input [31:0] seq_value, input [1:0] word_index);
        begin
            // 256 records x four 64-bit words. The low eight sequence bits
            // select the slot; the low two word-index bits select the record word.
            input_data_address = INPUT_DATA_BASE_WORD
                              + {19'd0, seq_value[7:0], 2'b00}
                              + {27'd0, word_index};
        end
    endfunction

    assign ddram_burstcnt = 8'd1;
    assign ddram_rd = (state == VERIFY_REQUEST) || (state == POLL_REQUEST);
    assign ddram_we = (state == WRITE_EVENT) || (state == PUBLISH_PRODUCER)
                    || (state == PUBLISH_DROPPED);
    assign ddram_addr = (state == VERIFY_REQUEST)
                      ? ((verify_index == 0) ? INPUT_CONTROL_WORD
                       : (verify_index == 1) ? INPUT_LAYOUT_WORD : INPUT_EPOCH_WORD)
                      : (state == PUBLISH_DROPPED)
                      ? INPUT_DROPPED_WORD
                      : ((state == POLL_REQUEST) || (state == POLL_WAIT))
                      ? INPUT_CONTROL_WORD
                      : (state == WRITE_EVENT)
                      ? input_data_address(event_sequence, write_index)
                      : INPUT_CONTROL_WORD;
    assign ddram_din = (state == WRITE_EVENT)
                     ? ((write_index == 0) ? {event_timestamp, event_sequence}
                        : (write_index == 1) ? {event_code, event_type}
                        : (write_index == 2) ? {event_value1, event_value0}
                        : event_buttons)
                     : (state == PUBLISH_DROPPED)
                     ? dropped_count
                     : {32'd0, producer_sequence + 1'b1};
    // FPGA owns the low producer half; all event records are full-word writes.
    assign ddram_be = (state == PUBLISH_PRODUCER) ? 8'h0f : 8'hff;

    always @(posedge clk) begin
        if (reset || !session_valid) begin
            state <= INACTIVE;
            verify_index <= 0;
            layout_valid <= 1'b0;
            verified_once <= 1'b0;
            active_epoch <= 0;
            producer_sequence <= 0;
            consumer_sequence <= 0;
            timestamp_counter <= 0;
            poll_counter <= 0;
            last_key_toggle <= 0;
            last_mouse_toggle <= 0;
            last_joystick <= 0;
            last_left_analog <= 0;
            last_right_analog <= 0;
            last_osd_status <= 1'b0;
            event_sequence <= 0;
            event_timestamp <= 0;
            event_type <= 0;
            event_code <= 0;
            event_value0 <= 0;
            event_value1 <= 0;
            event_buttons <= 0;
            write_index <= 0;
            dropped_count <= 0;
            ring_valid <= 1'b0;
            overflow_count <= 0;
        end else begin
            timestamp_counter <= timestamp_counter + 1'b1;

            if (active_epoch != session_epoch) begin
                state <= VERIFY_REQUEST;
                verify_index <= 0;
                layout_valid <= 1'b0;
                verified_once <= 1'b0;
                active_epoch <= session_epoch;
                producer_sequence <= 0;
                consumer_sequence <= 0;
                timestamp_counter <= 0;
                poll_counter <= 0;
                dropped_count <= 0;
                last_key_toggle <= ps2_key[10];
                last_mouse_toggle <= ps2_mouse[24];
                last_joystick <= joystick_0;
                last_left_analog <= joystick_l_analog_0;
                last_right_analog <= joystick_r_analog_0;
                last_osd_status <= osd_status;
                ring_valid <= 1'b0;
                overflow_count <= 0;
            end else begin
                case (state)
                    INACTIVE: begin
                        state <= VERIFY_REQUEST;
                        verify_index <= 0;
                    end

                    VERIFY_REQUEST: if (!ddram_busy) state <= VERIFY_WAIT;

                    VERIFY_WAIT: if (ddram_dout_ready) begin
                        case (verify_index)
                            0: begin
                                if (!verified_once) producer_sequence <= ddram_dout[31:0];
                                consumer_sequence <= ddram_dout[63:32];
                            end
                            1: layout_valid <= (ddram_dout[31:0] == DIABLO_TRANSPORT_INPUT_CAPACITY)
                                             && (ddram_dout[63:32] == DIABLO_TRANSPORT_INPUT_RECORD_BYTES);
                            default: begin
                                if (layout_valid && ddram_dout[31:0] == active_epoch) begin
                                    ring_valid <= 1'b1;
                                    verified_once <= 1'b1;
                                    poll_counter <= 0;
                                    state <= IDLE;
                                end else begin
                                    ring_valid <= 1'b0;
                                    poll_counter <= 0;
                                    state <= REVERIFY_WAIT;
                                end
                            end
                        endcase
                        if (verify_index != 2) begin
                            verify_index <= verify_index + 1'b1;
                            state <= VERIFY_REQUEST;
                        end
                    end

                    IDLE: begin
                        if (input_changed) begin
                            // Capture one edge at a time. A later change remains
                            // visible because only the selected source's baseline
                            // is advanced here.
                            if (key_changed) begin
                                last_key_toggle <= ps2_key[10];
                                if (ring_full) begin
                                    overflow_count <= overflow_count + 1'b1;
                                    dropped_count <= dropped_count + 1'b1;
                                    state <= PUBLISH_DROPPED;
                                end else begin
                                    event_type <= DIABLO_INPUT_EVENT_KEYBOARD;
                                    event_code <= keyboard_code;
                                    event_value0 <= {31'd0, ps2_key[9]};
                                    event_value1 <= 0;
                                    event_buttons <= current_buttons;
                                    event_sequence <= producer_sequence;
                                    event_timestamp <= timestamp_counter;
                                    write_index <= 0;
                                    state <= WRITE_EVENT;
                                end
                            end else if (mouse_changed) begin
                                last_mouse_toggle <= ps2_mouse[24];
                                if (ring_full) begin
                                    overflow_count <= overflow_count + 1'b1;
                                    dropped_count <= dropped_count + 1'b1;
                                    state <= PUBLISH_DROPPED;
                                end else begin
                                    event_type <= DIABLO_INPUT_EVENT_MOUSE;
                                    event_code <= mouse_code;
                                    event_value0 <= mouse_dx;
                                    event_value1 <= mouse_dy;
                                    event_buttons <= current_buttons;
                                    event_sequence <= producer_sequence;
                                    event_timestamp <= timestamp_counter;
                                    write_index <= 0;
                                    state <= WRITE_EVENT;
                                end
                            end else if (joystick_changed) begin
                                last_joystick <= joystick_0;
                                last_left_analog <= joystick_l_analog_0;
                                last_right_analog <= joystick_r_analog_0;
                                if (ring_full) begin
                                    overflow_count <= overflow_count + 1'b1;
                                    dropped_count <= dropped_count + 1'b1;
                                    state <= PUBLISH_DROPPED;
                                end else begin
                                    event_type <= DIABLO_INPUT_EVENT_JOYSTICK;
                                    event_code <= 0;
                                    event_value0 <= left_analog;
                                    event_value1 <= right_analog;
                                    event_buttons <= current_buttons;
                                    event_sequence <= producer_sequence;
                                    event_timestamp <= timestamp_counter;
                                    write_index <= 0;
                                    state <= WRITE_EVENT;
                                end
                            end else begin
                                last_osd_status <= osd_status;
                                if (ring_full) begin
                                    overflow_count <= overflow_count + 1'b1;
                                    dropped_count <= dropped_count + 1'b1;
                                    state <= PUBLISH_DROPPED;
                                end else begin
                                    event_type <= DIABLO_INPUT_EVENT_FOCUS;
                                    event_code <= 0;
                                    // The host maps zero to focus gained and one
                                    // to focus lost, so OSD open maps to lost.
                                    event_value0 <= {31'd0, osd_status};
                                    event_value1 <= 0;
                                    event_buttons <= current_buttons;
                                    event_sequence <= producer_sequence;
                                    event_timestamp <= timestamp_counter;
                                    write_index <= 0;
                                    state <= WRITE_EVENT;
                                end
                            end
                            poll_counter <= 0;
                        end else if (poll_counter == POLL_INTERVAL_LIMIT - 1) begin
                            poll_counter <= 0;
                            state <= POLL_REQUEST;
                        end else begin
                            poll_counter <= poll_counter + 1'b1;
                        end
                    end

                    WRITE_EVENT: if (!ddram_busy) begin
                        if (write_index == 3) begin
                            state <= PUBLISH_PRODUCER;
                        end else begin
                            write_index <= write_index + 1'b1;
                        end
                    end

                    PUBLISH_PRODUCER: if (!ddram_busy) begin
                        producer_sequence <= producer_sequence + 1'b1;
                        state <= IDLE;
                    end

                    PUBLISH_DROPPED: if (!ddram_busy) begin
                        state <= IDLE;
                    end

                    POLL_REQUEST: if (!ddram_busy) state <= POLL_WAIT;
                    POLL_WAIT: if (ddram_dout_ready) begin
                        consumer_sequence <= ddram_dout[63:32];
                        state <= IDLE;
                    end

                    REVERIFY_WAIT: begin
                        if (poll_counter == POLL_INTERVAL_LIMIT - 1) begin
                            poll_counter <= 0;
                            verify_index <= 0;
                            state <= VERIFY_REQUEST;
                        end else begin
                            poll_counter <= poll_counter + 1'b1;
                        end
                    end

                    default: state <= INACTIVE;
                endcase
            end
        end
    end
endmodule
