// SPDX-License-Identifier: GPL-2.0-or-later
// One-word ARM <-> FPGA DDR coherency preflight for the MiSTer shared-DDR
// aperture. It is separate from frame transport so that ownership, address
// units, ordering, and both directions are proven before frame consumption.
module diablo_ddr_probe #(
    parameter integer RETRY_DELAY_CYCLES = 500000,
    parameter integer MAX_ATTEMPTS = 16
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
    output reg pass = 1'b0,
    output reg fault = 1'b0
);
    // MiSTer's documented shared-DDR aperture is 0x20000000..0x3fffffff.
    // Its low address is used by platform services, so this core owns the
    // final 2 MiB. DDRAM_ADDR counts 64-bit words.
    localparam [28:0] SHARED_BASE_WORD = 29'h07FC0000; // 0x3fe00000 >> 3
    localparam [63:0] ARM_CHALLENGE = 64'hD1AB10F0C0DEC0DE;
    localparam [63:0] FPGA_ACK = 64'hF9A0BEEFC0DEC0DE;

    localparam [2:0] READ_REQUEST = 3'd0;
    localparam [2:0] READ_WAIT = 3'd1;
    localparam [2:0] WRITE_ACK = 3'd2;
    localparam [2:0] RETRY_WAIT = 3'd3;
    localparam [2:0] COMPLETE = 3'd4;

    reg [2:0] state = READ_REQUEST;
    reg [31:0] retry_count = 0;
    reg [7:0] attempts = 0;

    assign ddram_burstcnt = 8'd1;
    assign ddram_addr = (state == WRITE_ACK) ? (SHARED_BASE_WORD + 29'd1) : SHARED_BASE_WORD;
    assign ddram_rd = (state == READ_REQUEST);
    assign ddram_din = FPGA_ACK;
    assign ddram_be = 8'hff;
    assign ddram_we = (state == WRITE_ACK);

    always @(posedge clk) begin
        if (reset) begin
            state <= READ_REQUEST;
            retry_count <= 0;
            attempts <= 0;
            pass <= 1'b0;
            fault <= 1'b0;
        end else begin
            case (state)
                READ_REQUEST: if (!ddram_busy) state <= READ_WAIT;
                READ_WAIT: if (ddram_dout_ready) begin
                    if (ddram_dout == ARM_CHALLENGE) begin
                        fault <= 1'b0;
                        state <= WRITE_ACK;
                    end
                    else begin
                        attempts <= attempts + 1'b1;
                        retry_count <= 0;
                        state <= RETRY_WAIT;
                    end
                end
                WRITE_ACK: if (!ddram_busy) begin
                    pass <= 1'b1;
                    state <= COMPLETE;
                end
                RETRY_WAIT: begin
                    if (retry_count == RETRY_DELAY_CYCLES - 1) begin
                        if (attempts >= MAX_ATTEMPTS) begin
                            fault <= 1'b1;
                            attempts <= 0;
                        end
                        state <= READ_REQUEST;
                    end else retry_count <= retry_count + 1'b1;
                end
                default: state <= state;
            endcase
        end
    end
endmodule
