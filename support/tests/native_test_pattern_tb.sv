`timescale 1ns/1ps
module native_test_pattern_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg ready = 0, reset = 0;
    reg diagnostic_enable = 1, startup_error = 0;
    reg [1:0] mode = 0;
    wire ce, hs, vs, de;
    wire [7:0] r, g, b;
    native_test_pattern dut(
        .clk(clk), .ready(ready), .reset(reset), .mode(mode),
        .diagnostic_enable(diagnostic_enable), .startup_error(startup_error),
        .ddr_probe_pass(1'b0), .ddr_probe_fault(1'b0),
        .ce_pixel(ce), .hs(hs), .vs(vs), .de(de), .red(r), .green(g), .blue(b)
    );
    integer pixels = 0, active = 0, low_hs = 0, low_vs = 0;
    integer x, y, frame, ramp, last_ce = 0;
    integer i, saw_guard_black;
    reg [23:0] expected;
    reg [23:0] bars [0:7];
    initial begin
        bars[0]=24'hffffff; bars[1]=24'hffff00; bars[2]=24'h00ffff; bars[3]=24'h00ff00;
        bars[4]=24'hff00ff; bars[5]=24'hff0000; bars[6]=24'h0000ff; bars[7]=24'h000000;
        repeat (8) @(negedge clk);
        if (ce !== 0 || de !== 0) $fatal(1, "Video enabled before PLL ready");
        ready = 1;
        while (pixels < 800*525*3) begin
            @(negedge clk);
            if (ce === last_ce) $fatal(1, "Pixel enable does not alternate");
            last_ce = ce;
            if (ce) begin
                frame = pixels / (800*525);
                x = pixels % 800;
                y = (pixels / 800) % 525;
                if (hs !== !(x >= 656 && x <= 751)) $fatal(1, "Horizontal timing at %0d,%0d",x,y);
                if (vs !== !(y == 490 || y == 491)) $fatal(1, "Vertical timing at %0d,%0d",x,y);
                if (de !== (x < 640 && y < 480)) $fatal(1, "Active dimensions at %0d,%0d",x,y);
                expected = 0;
                if (de) begin
                    active = active + 1;
                    case (frame)
                        0: expected = bars[x/80];
                        1: begin
                            expected = ((x+y)%2) ? 24'hffffff : 24'h000000;
                            if (x==319 || y==239) expected=24'hff0000;
                        end
                        2: begin
                            ramp = x < 64 ? 0 : x > 575 ? 255 : (x-64)/2;
                            case (y/120)
                                0: expected = ramp * 65536;
                                1: expected = ramp * 256;
                                2: expected = ramp;
                                3: expected = ramp * 65793;
                            endcase
                        end
                    endcase
                    if (x==0 || x==639 || y==0 || y==479) expected=24'hffffff;
                end
                if ({r,g,b} !== expected) $fatal(1, "RGB mismatch frame %0d at %0d,%0d: %h != %h",frame,x,y,{r,g,b},expected);
                if (!hs) low_hs = low_hs + 1;
                if (!vs) low_vs = low_vs + 1;
                // Change the request during active drawing: it must wait for a frame boundary.
                if (x==100 && y==100 && frame<2) mode=frame+1;
                // A user reset pulse must not shorten a line/frame or blank active pixels.
                if (frame==1 && y==200 && x==123) reset=1;
                if (frame==1 && y==200 && x==155) reset=0;
                pixels = pixels + 1;
            end
        end
        if (active != 3*640*480 || low_hs != 3*96*525 || low_vs != 3*2*800)
            $fatal(1, "Frame timing totals differ");
        ready=0;
        repeat (4) @(negedge clk);
        if (ce !== 0 || de !== 0) $fatal(1, "PLL unlock must suppress video");
        // The source guard is an explicit contract: startup/fault remains
        // black until the framework framebuffer/scaler has a valid frame.
        diagnostic_enable = 0;
        startup_error = 1;
        ready = 1;
        saw_guard_black = 0;
        for (i = 0; i < 5000; i = i + 1) begin
            @(negedge clk);
            if (ce && de && {r,g,b} != 24'h000000)
                $fatal(1, "startup guard must remain black, got %h", {r,g,b});
            if (ce && de && {r,g,b} == 24'h000000)
                saw_guard_black = 1;
        end
        if (!saw_guard_black) $fatal(1, "startup guard did not blank direct bus");
        startup_error = 0;
        for (i = 0; i < 5000; i = i + 1) begin
            @(negedge clk);
            if (ce && de && {r,g,b} == 24'h000000) saw_guard_black = 1;
        end
        if (!saw_guard_black) $fatal(1, "normal gameplay guard did not blank direct bus");
        ready=0;
        repeat (4) @(negedge clk);
        if (ce !== 0 || de !== 0) $fatal(1, "PLL unlock must suppress video after source check");
        $display("PASS: three complete frames, CE cadence, sync/porches, 640x480, RGB, mode latching and reset continuity");
        $finish;
    end
    initial begin #30000000; $fatal(1,"Timeout"); end
endmodule
