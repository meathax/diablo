// SPDX-License-Identifier: GPL-2.0-or-later
// 25.2 MHz pixels: 800 clocks/line, 525 lines/frame = 60 Hz progressive.
module native_test_pattern (
    input wire clk,
    input wire ready,
    input wire reset,
    input wire [1:0] mode,
    input wire diagnostic_enable,
    input wire startup_error,
    input wire ddr_probe_pass,
    input wire ddr_probe_fault,
    output reg ce_pixel = 0,
    output wire hs,
    output wire vs,
    output wire de,
    output reg [7:0] red,
    output reg [7:0] green,
    output reg [7:0] blue
);
    reg [9:0] x = 0;
    reg [9:0] y = 0;
    reg [1:0] selected = 0;
    always @(posedge clk) begin
        if (!ready) begin
            ce_pixel <= 0;
            x <= 0;
            y <= 0;
            selected <= 0;
        end else begin
            ce_pixel <= ~ce_pixel;
            if (ce_pixel) begin
                if (x == 799) begin
                    x <= 0;
                    y <= y == 524 ? 10'd0 : y + 10'd1;
                end else x <= x + 10'd1;
                // OSD mode changes and user reset never interrupt sync timing.
                if (x == 0 && y == 0) selected <= reset ? 2'd0 : mode;
            end
        end
    end
    assign hs = !(x >= 656 && x < 752);
    assign vs = !(y >= 490 && y < 492);
    assign de = ready && x < 640 && y < 480;
    wire border = x == 0 || x == 639 || y == 0 || y == 479;
    wire [9:0] ramp_position = x - 10'd64;
    wire [7:0] ramp = x < 64 ? 8'd0 : x >= 576 ? 8'd255 : ramp_position[8:1];
    always @* begin
        red = 0;
        green = 0;
        blue = 0;
        if (de) begin
            if (!diagnostic_enable) begin
                // Keep the direct RGB bus completely black until the
                // framebuffer/scaler has a valid gameplay frame.  Startup
                // faults are reported through the transport diagnostics, not
                // by drawing a debug pattern over the boot screen.
                {red, green, blue} = 24'h000000;
            end else begin
                case (selected)
                    2'd1: begin
                        {red, green, blue} = (x[0] ^ y[0]) ? 24'hffffff : 24'h000000;
                        if (x == 319 || y == 239) {red, green, blue} = 24'hff0000;
                    end
                    2'd2: begin
                        if (y < 120) red = ramp;
                        else if (y < 240) green = ramp;
                        else if (y < 360) blue = ramp;
                        else {red, green, blue} = {ramp, ramp, ramp};
                    end
                    default: begin
                        if      (x < 80)  {red, green, blue} = 24'hffffff;
                        else if (x < 160) {red, green, blue} = 24'hffff00;
                        else if (x < 240) {red, green, blue} = 24'h00ffff;
                        else if (x < 320) {red, green, blue} = 24'h00ff00;
                        else if (x < 400) {red, green, blue} = 24'hff00ff;
                        else if (x < 480) {red, green, blue} = 24'hff0000;
                        else if (x < 560) {red, green, blue} = 24'h0000ff;
                    end
                endcase
            end
            // Board-visible DDR preflight marker is available only on an
            // explicitly selected diagnostic screen.
            if (diagnostic_enable && x < 128 && y < 24) begin
                if (ddr_probe_pass) {red, green, blue} = 24'h00ff00;
                else if (ddr_probe_fault) {red, green, blue} = 24'hff0000;
            end
            if (diagnostic_enable && border) {red, green, blue} = 24'hffffff;
        end
    end
endmodule
