// SPDX-License-Identifier: GPL-2.0-or-later
// Bounded FPGA attachment check for the ARM-owned transport control page.
// It reads only fixed ABI v1 words, validates identity and the three initial
// frame descriptors, then publishes the FPGA component state. No frame pixels
// are fetched until a later scanout stage owns this endpoint.
module diablo_transport_control_reader #(
    parameter integer RETRY_DELAY_CYCLES = 500000,
    parameter integer RECHECK_DELAY_CYCLES = 5000000
) (
    input wire clk,
    input wire reset,
    input wire ddram_busy,
    input wire [63:0] ddram_dout,
    input wire ddram_dout_ready,
    output wire [7:0] ddram_burstcnt,
    output wire [28:0] ddram_addr,
    output wire ddram_rd,
    output wire [63:0] ddram_din,
    output wire [7:0] ddram_be,
    output wire ddram_we,
    output reg attached = 1'b0,
    output reg fault = 1'b0,
    output reg [31:0] attached_epoch = 0
);
    `include "diablo_transport_abi.svh"

    // The final 2 MiB of the target-reserved 0x20000000..0x3fffffff aperture.
    // DDRAM_ADDR is a 64-bit word address, not a byte address.
    localparam [28:0] SHARED_BASE_WORD = 29'h07FC0000;
    localparam [4:0] LAST_READ_INDEX = 5'd16;

    localparam [3:0] READ_REQUEST = 4'd0;
    localparam [3:0] READ_WAIT = 4'd1;
    localparam [3:0] VALIDATE = 4'd2;
    localparam [3:0] WRITE_READY = 4'd3;
    localparam [3:0] WRITE_CLEAR_FAULT = 4'd4;
    localparam [3:0] WRITE_FAULT_CODE = 4'd5;
    localparam [3:0] WRITE_FAULT_STATE = 4'd6;
    localparam [3:0] RETRY_WAIT = 4'd7;
    localparam [3:0] COMPLETE = 4'd8;

    reg [3:0] state = READ_REQUEST;
    reg [4:0] read_index = 0;
    reg [63:0] read_data = 0;
    reg [31:0] session_epoch = 0;
    reg [31:0] arm_state = 0;
    reg [31:0] fault_code = 0;
    reg [31:0] fault_detail = 0;
    reg [31:0] retry_count = 0;
    reg [31:0] recheck_count = 0;
    reg monitor_only = 1'b0;

    function automatic [28:0] read_address(input [4:0] index);
        begin
            case (index)
                5'd0: read_address = SHARED_BASE_WORD;       // magic
                5'd1: read_address = SHARED_BASE_WORD + 1;   // ABI/control size
                5'd2: read_address = SHARED_BASE_WORD + 2;   // shared size/endian tag
                5'd3: read_address = SHARED_BASE_WORD + 3;   // capabilities/session epoch
                5'd4: read_address = SHARED_BASE_WORD + 4;   // ARM/FPGA component states
                5'd5: read_address = SHARED_BASE_WORD + 22;  // slot 0 state/generation
                5'd6: read_address = SHARED_BASE_WORD + 25;  // slot 0 pixel offset/size
                5'd7: read_address = SHARED_BASE_WORD + 26;  // slot 0 palette offset/size
                5'd8: read_address = SHARED_BASE_WORD + 27;  // slot 0 producer/display epoch
                5'd9: read_address = SHARED_BASE_WORD + 30;  // slot 1 state/generation
                5'd10: read_address = SHARED_BASE_WORD + 33; // slot 1 pixel offset/size
                5'd11: read_address = SHARED_BASE_WORD + 34; // slot 1 palette offset/size
                5'd12: read_address = SHARED_BASE_WORD + 35; // slot 1 producer/display epoch
                5'd13: read_address = SHARED_BASE_WORD + 38; // slot 2 state/generation
                5'd14: read_address = SHARED_BASE_WORD + 41; // slot 2 pixel offset/size
                5'd15: read_address = SHARED_BASE_WORD + 42; // slot 2 palette offset/size
                default: read_address = SHARED_BASE_WORD + 43; // slot 2 producer/display epoch
            endcase
        end
    endfunction

    function automatic [31:0] slot_for_index(input [4:0] index);
        begin
            if (index < 9) slot_for_index = 0;
            else if (index < 13) slot_for_index = 1;
            else slot_for_index = 2;
        end
    endfunction

    function automatic valid_read(input [4:0] index, input [63:0] word);
        reg [31:0] slot;
        begin
            case (index)
                5'd0: valid_read = (word == DIABLO_TRANSPORT_MAGIC_LE64);
                5'd1: valid_read = (word[15:0] == DIABLO_TRANSPORT_ABI_MAJOR)
                                  && (word[31:16] == DIABLO_TRANSPORT_ABI_MINOR)
                                  && (word[63:32] == DIABLO_TRANSPORT_CONTROL_BYTES);
                5'd2: valid_read = (word[31:0] == DIABLO_TRANSPORT_SHARED_BYTES)
                                  && (word[63:32] == DIABLO_TRANSPORT_LITTLE_ENDIAN_TAG);
                5'd3: valid_read = (word[63:32] != 0);
                5'd4: valid_read = (word[31:0] == DIABLO_COMPONENT_READY);
                default: begin
                    slot = slot_for_index(index);
                    case ((index - 5'd5) & 5'd3)
                        // A live ARM process may publish a frame before the
                        // FPGA notices an epoch change during a relaunch. The
                        // descriptor is still valid in every ownership state
                        // except FAULT; accepting 0..4 lets the reader attach
                        // without requiring a second RBF load.
                        0: valid_read = (word[31:0] <= DIABLO_FRAME_RETIRED)
                                     && (word[63:32] == session_epoch);
                        1: valid_read = (word[31:0] == diablo_transport_frame_offset(slot))
                                     && (word[63:32] == DIABLO_TRANSPORT_FRAME_PIXEL_BYTES);
                        2: valid_read = (word[31:0] == diablo_transport_palette_offset(slot))
                                     && (word[63:32] == DIABLO_TRANSPORT_PALETTE_BYTES);
                        // The ARM owns producer_epoch (low half); the FPGA
                        // owns display_epoch (high half) and advances it at
                        // every vblank retirement. A freshly initialized ARM
                        // page legitimately carries zero here, so this field
                        // is intentionally unconstrained during attachment.
                        default: valid_read = 1'b1;
                    endcase
                end
            endcase
        end
    endfunction

    function automatic [31:0] error_for_index(input [4:0] index);
        begin
            case (index)
                5'd0: error_for_index = 32'd1; // identity magic
                5'd1, 5'd2: error_for_index = 32'd2; // ABI/layout
                5'd3, 5'd4: error_for_index = 32'd3; // session/component state
                default: error_for_index = 32'd16 + index - 5'd5; // slot field
            endcase
        end
    endfunction

    assign ddram_burstcnt = 8'd1;
    assign ddram_addr = (state == WRITE_READY || state == WRITE_FAULT_STATE)
                      ? (SHARED_BASE_WORD + 29'd4)
                      : (state == WRITE_CLEAR_FAULT || state == WRITE_FAULT_CODE)
                      ? (SHARED_BASE_WORD + 29'd5)
                      : read_address(read_index);
    assign ddram_rd = (state == READ_REQUEST);
    assign ddram_we = (state == WRITE_READY) || (state == WRITE_CLEAR_FAULT)
                   || (state == WRITE_FAULT_CODE)
                   || (state == WRITE_FAULT_STATE);
    // Header arm_state occupies the low 32 bits of word four and is owned by
    // the ARM. FPGA status occupies the upper 32 bits. A fault found while
    // the ARM is publishing a new header must never overwrite arm_state.
    assign ddram_be = (state == WRITE_CLEAR_FAULT || state == WRITE_FAULT_CODE) ? 8'hff : 8'hf0;
    assign ddram_din = (state == WRITE_READY)
                     ? {DIABLO_COMPONENT_READY, arm_state}
                     : (state == WRITE_CLEAR_FAULT)
                     ? 64'd0
                     : (state == WRITE_FAULT_CODE)
                     ? {fault_detail, fault_code}
                     : {DIABLO_COMPONENT_FAULT, arm_state};

    always @(posedge clk) begin
        if (reset) begin
            state <= READ_REQUEST;
            read_index <= 0;
            read_data <= 0;
            session_epoch <= 0;
            attached_epoch <= 0;
            arm_state <= 0;
            fault_code <= 0;
            fault_detail <= 0;
            retry_count <= 0;
            recheck_count <= 0;
            monitor_only <= 1'b0;
            attached <= 1'b0;
            fault <= 1'b0;
        end else begin
            case (state)
                READ_REQUEST: if (!ddram_busy) state <= READ_WAIT;
                READ_WAIT: if (ddram_dout_ready) begin
                    read_data <= ddram_dout;
                    state <= VALIDATE;
                end
                VALIDATE: begin
                    if (monitor_only) begin
                        // COMPLETE keeps the transport attached while it
                        // checks the publication marker, epoch and ARM state.
                        // A changed session detaches first, then runs the
                        // complete bounded validation below. Unchanged pages
                        // never disturb scanout/audio/input ownership.
                        if ((read_index == 5'd0 && read_data != DIABLO_TRANSPORT_MAGIC_LE64)
                         || (read_index == 5'd3 && read_data[63:32] != session_epoch)
                         || (read_index == 5'd4 && read_data[31:0] != DIABLO_COMPONENT_READY)) begin
                            attached <= 1'b0;
                            attached_epoch <= 0;
                            session_epoch <= 0;
                            arm_state <= 0;
                            monitor_only <= 1'b0;
                            read_index <= 0;
                            // Leave a complete DDR response window before
                            // starting the full validation. During a live ARM
                            // relaunch the marker and epoch can change while
                            // the arbiter still presents the previous monitor
                            // read response; entering the bounded retry state
                            // prevents that stale response from poisoning the
                            // first descriptor read of the new page.
                            retry_count <= 0;
                            state <= RETRY_WAIT;
                        end else if (read_index == 5'd0) begin
                            read_index <= 5'd3;
                            state <= READ_REQUEST;
                        end else if (read_index == 5'd3) begin
                            read_index <= 5'd4;
                            state <= READ_REQUEST;
                        end else begin
                            monitor_only <= 1'b0;
                            recheck_count <= 0;
                            state <= COMPLETE;
                        end
                    end else if (valid_read(read_index, read_data)) begin
                        if (read_index == 5'd3) session_epoch <= read_data[63:32];
                        if (read_index == 5'd4) arm_state <= read_data[31:0];
                        if (read_index == LAST_READ_INDEX) state <= WRITE_READY;
                        else begin
                            read_index <= read_index + 1'b1;
                            state <= READ_REQUEST;
                        end
                    end else begin
                        fault_code <= error_for_index(read_index);
                        fault_detail <= read_data[31:0];
                        state <= WRITE_FAULT_CODE;
                    end
                end
                WRITE_READY: if (!ddram_busy) state <= WRITE_CLEAR_FAULT;
                WRITE_CLEAR_FAULT: if (!ddram_busy) begin
                    attached <= 1'b1;
                    fault <= 1'b0;
                    attached_epoch <= session_epoch;
                    recheck_count <= 0;
                    monitor_only <= 1'b0;
                    state <= COMPLETE;
                end
                WRITE_FAULT_CODE: if (!ddram_busy) state <= WRITE_FAULT_STATE;
                WRITE_FAULT_STATE: if (!ddram_busy) begin
                    attached <= 1'b0;
                    fault <= 1'b1;
                    attached_epoch <= 0;
                    retry_count <= 0;
                    recheck_count <= 0;
                    monitor_only <= 1'b0;
                    state <= RETRY_WAIT;
                end
                RETRY_WAIT: begin
                    if (retry_count == RETRY_DELAY_CYCLES - 1) begin
                        read_index <= 0;
                        session_epoch <= 0;
                        arm_state <= 0;
                        recheck_count <= 0;
                        state <= READ_REQUEST;
                    end else retry_count <= retry_count + 1'b1;
                end
                COMPLETE: begin
                    if (recheck_count == RECHECK_DELAY_CYCLES - 1) begin
                        // Read the publication marker, session epoch and ARM
                        // state without interrupting a healthy attachment.
                        recheck_count <= 0;
                        monitor_only <= 1'b1;
                        read_index <= 0;
                        state <= READ_REQUEST;
                    end else begin
                        recheck_count <= recheck_count + 1'b1;
                    end
                end
                default: state <= state;
            endcase
        end
    end
endmodule
