`timescale 1ns/1ps
module diablo_framebuffer_scanout_tb;
    localparam [31:0] EPOCH = 32'hd1a61001;
    localparam [28:0] BASE_WORD = 29'h07fc0000;
    localparam [28:0] PALETTE0_WORD = BASE_WORD + 29'd38912;
    localparam [28:0] PALETTE1_WORD = BASE_WORD + 29'd77824;

    reg clk = 0;
    reg fb_pal_clk = 0;
    always #5 clk = ~clk;
    always #7 fb_pal_clk = ~fb_pal_clk;

    reg reset = 1;
    reg session_valid = 0;
    reg [31:0] session_epoch = EPOCH;
    reg vblank = 0;
    reg frame_rate_cap = 0;
    reg ddram_busy = 0;
    reg [63:0] ddram_dout = 0;
    reg ddram_dout_ready = 0;
    wire [7:0] ddram_burstcnt;
    wire [28:0] ddram_addr;
    wire ddram_rd;
    wire [63:0] ddram_din;
    wire [7:0] ddram_be;
    wire ddram_we;
    wire framebuffer_valid;
    wire [31:0] framebuffer_base;
    wire framebuffer_blank;
    wire [7:0] fb_pal_addr;
    wire [23:0] fb_pal_dout;
    wire fb_pal_wr;

    reg [31:0] frame_state [0:2];
    reg [31:0] frame_generation [0:2];
    reg [63:0] frame_id [0:2];
    reg read_pending = 0;
    reg [28:0] read_address = 0;
    integer display_writes = 0;
    integer free_writes = 0;
    integer palette_writes = 0;
    reg [31:0] frame_display_epoch [0:2];
    reg [63:0] last_presented_frame_id = 0;
    reg [31:0] header_display_epoch = 0;

    diablo_framebuffer_scanout dut (
        .clk(clk), .reset(reset), .session_valid(session_valid), .session_epoch(session_epoch), .vblank(vblank), .frame_rate_cap(frame_rate_cap),
        .ddram_busy(ddram_busy), .ddram_dout(ddram_dout), .ddram_dout_ready(ddram_dout_ready),
        .ddram_burstcnt(ddram_burstcnt), .ddram_addr(ddram_addr), .ddram_rd(ddram_rd),
        .ddram_din(ddram_din), .ddram_be(ddram_be), .ddram_we(ddram_we),
        .framebuffer_valid(framebuffer_valid), .framebuffer_base(framebuffer_base), .framebuffer_blank(framebuffer_blank),
        .fb_pal_clk(fb_pal_clk), .fb_pal_addr(fb_pal_addr), .fb_pal_dout(fb_pal_dout), .fb_pal_wr(fb_pal_wr)
    );

    function automatic [63:0] read_word(input [28:0] address);
        begin
            if (address == BASE_WORD + 29'd22) read_word = {frame_generation[0], frame_state[0]};
            else if (address == BASE_WORD + 29'd23) read_word = frame_id[0];
            else if (address == BASE_WORD + 29'd30) read_word = {frame_generation[1], frame_state[1]};
            else if (address == BASE_WORD + 29'd31) read_word = frame_id[1];
            else if (address == BASE_WORD + 29'd38) read_word = {frame_generation[2], frame_state[2]};
            else if (address == BASE_WORD + 29'd39) read_word = frame_id[2];
            else if ((address >= PALETTE0_WORD && address < PALETTE0_WORD + 96)
                  || (address >= PALETTE1_WORD && address < PALETTE1_WORD + 96)) read_word = 64'h0706050403020100;
            else begin
                $display("FAIL unexpected DDR read address %h", address);
                $fatal(1);
            end
        end
    endfunction

    always @(posedge clk) begin
        ddram_dout_ready <= 0;
        ddram_busy <= 0;
        if (read_pending) begin
            ddram_dout <= read_word(read_address);
            ddram_dout_ready <= 1;
            read_pending <= 0;
        end
        if (ddram_rd && !ddram_busy && !read_pending) begin
            if (ddram_burstcnt != 1) begin
                $display("FAIL expected single safe DDR read, got burst %d", ddram_burstcnt);
                $fatal(1);
            end
            read_pending <= 1;
            read_address <= ddram_addr;
            ddram_busy <= 1;
        end
        if (ddram_we && !ddram_busy) begin
            if (ddram_be == 8'h0f && ddram_addr == BASE_WORD + 29'd22) frame_state[0] <= ddram_din[31:0];
            else if (ddram_be == 8'h0f && ddram_addr == BASE_WORD + 29'd30) frame_state[1] <= ddram_din[31:0];
            else if (ddram_be == 8'h0f && ddram_addr == BASE_WORD + 29'd38) frame_state[2] <= ddram_din[31:0];
            else if (ddram_be == 8'hf0 && ddram_addr == BASE_WORD + 29'd27) begin
                frame_display_epoch[0] <= ddram_din[63:32];
                if (ddram_din[31:0] !== EPOCH) $fatal(1, "FAIL producer epoch clobbered");
            end else if (ddram_be == 8'hf0 && ddram_addr == BASE_WORD + 29'd35) begin
                frame_display_epoch[1] <= ddram_din[63:32];
                if (ddram_din[31:0] !== EPOCH) $fatal(1, "FAIL producer epoch clobbered");
            end else if (ddram_be == 8'hf0 && ddram_addr == BASE_WORD + 29'd43) begin
                frame_display_epoch[2] <= ddram_din[63:32];
                if (ddram_din[31:0] !== EPOCH) $fatal(1, "FAIL producer epoch clobbered");
            end else if (ddram_be == 8'hff && ddram_addr == BASE_WORD + 29'd46)
                last_presented_frame_id <= ddram_din;
            else if (ddram_be == 8'h0f && ddram_addr == BASE_WORD + 29'd48)
                header_display_epoch <= ddram_din[31:0];
            else begin
                $display("FAIL unexpected frame ownership write address=%h be=%h", ddram_addr, ddram_be);
                $fatal(1);
            end
            if (ddram_be == 8'h0f && ddram_din[31:0] == 3) display_writes <= display_writes + 1;
            if (ddram_be == 8'h0f && ddram_din[31:0] == 0) free_writes <= free_writes + 1;
            ddram_busy <= 1;
        end
    end

    always @(posedge fb_pal_clk) begin
        if (fb_pal_wr) begin
			if (!vblank) begin
				$display("FAIL palette write escaped vertical blank");
				$fatal(1);
			end
            palette_writes <= palette_writes + 1;
            if (fb_pal_addr == 0 && fb_pal_dout !== 24'h000102) begin
                $display("FAIL palette order is %h", fb_pal_dout);
                $fatal(1);
            end
        end
    end

    task automatic pulse_vblank;
        begin
            @(posedge clk);
            vblank <= 1;
            // A real vertical blank is far longer than one core cycle. Keep
            // this modeled interval long enough for the staged 256-entry
            // palette upload and its CDC acknowledgement to complete.
            repeat (512) @(posedge clk);
            vblank <= 0;
        end
    endtask

    task automatic wait_for_palette_stage;
        integer cycles;
        begin
            cycles = 0;
            while (dut.state != 9 && cycles < 20000) begin
                @(posedge clk);
                cycles = cycles + 1;
            end
            if (dut.state != 9) begin
                $display("FAIL frame did not finish descriptor and palette staging");
                $fatal(1);
            end
        end
    endtask

    integer slot;
    initial begin
        for (slot = 0; slot < 3; slot = slot + 1) begin
            frame_state[slot] = 0;
            frame_generation[slot] = EPOCH;
            frame_id[slot] = 0;
            frame_display_epoch[slot] = 0;
        end
        repeat (4) @(posedge clk);
        reset = 0;
        session_valid = 1;

        frame_state[0] = 2;
        frame_id[0] = 7;
        wait_for_palette_stage();
        pulse_vblank();
        repeat (4) @(posedge clk);
        if (!framebuffer_valid || framebuffer_blank || framebuffer_base !== 32'h3fe01000 || frame_state[0] !== 3) begin
            $display("FAIL first frame switch valid=%b blank=%b base=%h state=%d", framebuffer_valid, framebuffer_blank, framebuffer_base, frame_state[0]);
            $fatal(1);
        end

        // This descriptor is already stale before the next prepared frame.
        // It must be explicitly released, not stranded in READY forever.
        frame_state[2] = 2;
        frame_id[2] = 6;
        frame_state[1] = 2;
        frame_id[1] = 8;
        // The next descriptor is staged between refreshes. Requiring another
        // vblank just to begin this work would halve display cadence.
        wait_for_palette_stage();
        pulse_vblank();
        repeat (4) @(posedge clk);
        if (framebuffer_blank || framebuffer_base !== 32'h3fe4d000 || frame_state[1] !== 3) begin
            $display("FAIL second frame switch blank=%b base=%h state=%d", framebuffer_blank, framebuffer_base, frame_state[1]);
            $fatal(1);
        end
        // Frame two becomes active at the immediately following refresh after
        // it was ready. Retirement of frame one is already underway.
        repeat (20) @(posedge clk);
        if (frame_state[0] !== 0 || frame_state[2] !== 0 || display_writes != 2 || free_writes != 2 || palette_writes < 512
            || frame_display_epoch[0] !== 1 || last_presented_frame_id !== 7 || header_display_epoch !== 1) begin
            $display("FAIL ownership writes display=%d free=%d palette=%d oldstate=%d stalestate=%d frame_epoch=%d last=%d header_epoch=%d",
                     display_writes, free_writes, palette_writes, frame_state[0], frame_state[2], frame_display_epoch[0],
                     last_presented_frame_id, header_display_epoch);
            $fatal(1);
        end

        // With the cap enabled, a prepared frame can only replace the active
        // framebuffer on every third refresh. The frame is held for the two
        // intervening refreshes, so pacing is regular rather than jittery.
        frame_rate_cap = 1;
        frame_state[0] = 2;
        frame_id[0] = 9;
        wait_for_palette_stage();
        pulse_vblank();
        repeat (4) @(posedge clk);
        if (framebuffer_base !== 32'h3fe4d000 || dut.active_frame_id !== 8) begin
            $display("FAIL framerate cap switched on first refresh base=%h active=%d", framebuffer_base, dut.active_frame_id);
            $fatal(1);
        end
        pulse_vblank();
        repeat (4) @(posedge clk);
        if (framebuffer_base !== 32'h3fe4d000 || dut.active_frame_id !== 8) begin
            $display("FAIL framerate cap switched on second refresh base=%h active=%d", framebuffer_base, dut.active_frame_id);
            $fatal(1);
        end
        pulse_vblank();
        repeat (4) @(posedge clk);
        if (framebuffer_base !== 32'h3fe01000 || dut.active_frame_id !== 9 || frame_state[0] !== 3) begin
            $display("FAIL framerate cap missed third refresh base=%h active=%d state=%d", framebuffer_base, dut.active_frame_id, frame_state[0]);
            $fatal(1);
        end
        $display("framebuffer scanout checks passed");
        $finish;
    end
endmodule
