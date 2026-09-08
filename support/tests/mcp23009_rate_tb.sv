`timescale 1ns/1ps

// Actual MCP23009 plus standalone divider regression.  The production module
// is always exercised at its compiled 375 kHz setting; the second i2c instance
// makes the historical 500/400 kHz settings executable without changing the
// production module's parameterization.
module mcp23009_rate_tb;
    parameter integer RATE = 375_000;
    parameter integer EXPECT_PASS = 1;

    reg clk = 1'b0;
    reg [2:0] led = 3'b101;

    wire [2:0] btn;
    wire flg_sd_cd;
    wire flg_present;
    wire flg_mode;
    tri1 dut_scl;
    tri1 dut_sda;
    tri1 rate_scl;
    tri1 rate_sda;

    // Always acknowledge both buses while preserving open-drain resolution.
    assign dut_sda = 1'b0;
    assign rate_sda = 1'b0;

    // This is the actual production module under test.
    mcp23009 dut (
        .clk(clk),
        .btn(btn),
        .led(led),
        .flg_sd_cd(flg_sd_cd),
        .flg_present(flg_present),
        .flg_mode(flg_mode),
        .scl(dut_scl),
        .sda(dut_sda)
    );

    // Exercise each historical/current divider setting with the same i2c
    // transaction protocol and an ACKing open-drain slave.
    reg rate_start = 1'b0;
    wire rate_end;
    wire rate_ack;
    wire [7:0] rate_rdata;
    i2c #(50_000_000, RATE) rate_i2c (
        .CLK(clk),
        .START(rate_start),
        .READ(1'b0),
        .I2C_ADDR(7'h20),
        .I2C_WLEN(1'b1),
        .I2C_WDATA1(8'h00),
        .I2C_WDATA2(8'hF8),
        .I2C_RDATA(rate_rdata),
        .END(rate_end),
        .ACK(rate_ack),
        .I2C_SCL(rate_scl),
        .I2C_SDA(rate_sda)
    );

    always #10 clk = ~clk;

    integer dut_starts = 0;
    integer dut_completions = 0;
    integer dut_errors = 0;
    integer rate_starts = 0;
    integer rate_completions = 0;
    integer rate_errors = 0;
    integer dut_high_min_ns = 2_000_000_000;
    integer dut_high_max_ns = 0;
    integer dut_low_min_ns = 2_000_000_000;
    integer dut_low_max_ns = 0;
    integer dut_period_min_ns = 2_000_000_000;
    integer dut_period_max_ns = 0;
    integer rate_high_min_ns = 2_000_000_000;
    integer rate_high_max_ns = 0;
    integer rate_low_min_ns = 2_000_000_000;
    integer rate_low_max_ns = 0;
    integer rate_period_min_ns = 2_000_000_000;
    integer rate_period_max_ns = 0;
    integer dut_high_samples = 0;
    integer dut_low_samples = 0;
    integer dut_period_samples = 0;
    integer rate_high_samples = 0;
    integer rate_low_samples = 0;
    integer rate_period_samples = 0;
    integer delta_ns;
    time dut_last_rise = 0;
    time dut_last_fall = 0;
    time rate_last_rise = 0;
    time rate_last_fall = 0;
    reg previous_dut_ready = 1'b1;
    reg previous_dut_start = 1'b0;
    reg [1:0] rate_state = 0;

    always @(posedge clk) begin
        if (!previous_dut_start && dut.start)
            dut_starts = dut_starts + 1;
        if (!previous_dut_ready && dut.ready) begin
            dut_completions = dut_completions + 1;
            if (dut.error)
                dut_errors = dut_errors + 1;
        end
        previous_dut_start = dut.start;
        previous_dut_ready = dut.ready;

        case (rate_state)
            0: if (rate_completions < 3) begin
                rate_start <= 1'b1;
                rate_starts = rate_starts + 1;
                rate_state <= 1;
            end
            1: begin
                rate_start <= 1'b0;
                if (!rate_end)
                    rate_state <= 2;
            end
            2: if (rate_end) begin
                rate_completions = rate_completions + 1;
                if (rate_ack)
                    rate_errors = rate_errors + 1;
                rate_state <= 0;
            end
        endcase
    end

    always @(posedge dut_scl) begin
        if (dut_last_rise != 0) begin
            delta_ns = $time - dut_last_rise;
            if (delta_ns < dut_period_min_ns) dut_period_min_ns = delta_ns;
            if (delta_ns > dut_period_max_ns) dut_period_max_ns = delta_ns;
            dut_period_samples = dut_period_samples + 1;
        end
        if (dut_last_fall != 0) begin
            delta_ns = $time - dut_last_fall;
            if (delta_ns < dut_low_min_ns) dut_low_min_ns = delta_ns;
            if (delta_ns > dut_low_max_ns) dut_low_max_ns = delta_ns;
            dut_low_samples = dut_low_samples + 1;
        end
        dut_last_rise = $time;
    end

    always @(negedge dut_scl) begin
        if (dut_last_rise != 0) begin
            delta_ns = $time - dut_last_rise;
            if (delta_ns < dut_high_min_ns) dut_high_min_ns = delta_ns;
            if (delta_ns > dut_high_max_ns) dut_high_max_ns = delta_ns;
            dut_high_samples = dut_high_samples + 1;
        end
        dut_last_fall = $time;
    end

    always @(posedge rate_scl) begin
        if (rate_last_rise != 0) begin
            delta_ns = $time - rate_last_rise;
            if (delta_ns < rate_period_min_ns) rate_period_min_ns = delta_ns;
            if (delta_ns > rate_period_max_ns) rate_period_max_ns = delta_ns;
            rate_period_samples = rate_period_samples + 1;
        end
        if (rate_last_fall != 0) begin
            delta_ns = $time - rate_last_fall;
            if (delta_ns < rate_low_min_ns) rate_low_min_ns = delta_ns;
            if (delta_ns > rate_low_max_ns) rate_low_max_ns = delta_ns;
            rate_low_samples = rate_low_samples + 1;
        end
        rate_last_rise = $time;
    end

    always @(negedge rate_scl) begin
        if (rate_last_rise != 0) begin
            delta_ns = $time - rate_last_rise;
            if (delta_ns < rate_high_min_ns) rate_high_min_ns = delta_ns;
            if (delta_ns > rate_high_max_ns) rate_high_max_ns = delta_ns;
            rate_high_samples = rate_high_samples + 1;
        end
        rate_last_fall = $time;
    end

    initial begin
        // i2c.v has no reset port; seed free-running divider state to model
        // the hardware power-up state and avoid unknown simulation values.
        dut.i2c.cnt = 0;
        dut.i2c.I2C_CLOCK = 1'b0;
        rate_i2c.cnt = 0;
        rate_i2c.I2C_CLOCK = 1'b0;

        #8_000_000;
        $display("RATE=%0d dut_tx=%0d/%0d/%0d dut_high_ns=%0d..%0d dut_low_ns=%0d..%0d dut_period_ns=%0d..%0d rate_tx=%0d/%0d/%0d rate_high_ns=%0d..%0d rate_low_ns=%0d..%0d rate_period_ns=%0d..%0d samples=%0d/%0d/%0d",
                 RATE, dut_starts, dut_completions, dut_errors,
                 dut_high_min_ns, dut_high_max_ns, dut_low_min_ns,
                 dut_low_max_ns, dut_period_min_ns, dut_period_max_ns,
                 rate_starts, rate_completions, rate_errors,
                 rate_high_min_ns, rate_high_max_ns, rate_low_min_ns,
                 rate_low_max_ns, rate_period_min_ns, rate_period_max_ns,
                 rate_high_samples, rate_low_samples, rate_period_samples);
        $display("DUT_STATE start=%0d ready=%0d error=%0d i2c_end=%0d cnt=%0d clock=%0d",
                 dut.start, dut.ready, dut.error, dut.i2c.END,
                 dut.i2c.cnt, dut.i2c.I2C_CLOCK);

        if (dut_completions < 2 || dut_starts < 2 || dut_errors != 0)
            $fatal(1, "actual MCP23009 transaction did not complete cleanly");
        if (rate_completions < 2 || rate_starts < 2 || rate_errors != 0)
            $fatal(1, "divider transaction did not complete cleanly");
        if (dut_low_samples == 0 || dut_high_samples == 0 ||
            dut_period_samples == 0 || dut_low_min_ns < 1300 ||
            dut_high_min_ns < 600 || dut_period_min_ns < 2500)
            $fatal(1, "corrected MCP23009 timing contract failed");

        if (EXPECT_PASS) begin
            if (RATE != 375_000 || rate_low_min_ns < 1300 ||
                rate_high_min_ns < 600 || rate_period_min_ns < 2500)
                $fatal(1, "375 kHz divider timing contract failed");
            $display("PASS corrected 375 kHz Fast-mode timing and ACKed transactions");
        end else begin
            if (rate_low_min_ns >= 1300 && rate_period_min_ns >= 2500)
                $fatal(1, "legacy rate unexpectedly met the 400 kHz timing contract");
            $display("PASS legacy rate rejected by Fast-mode timing contract");
        end
        $finish;
    end
endmodule
