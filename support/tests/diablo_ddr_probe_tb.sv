`timescale 1ns/1ps
module diablo_ddr_probe_tb;
    reg clk = 0;
    always #5 clk = ~clk;
    reg reset = 1;
    reg busy = 1;
    reg [63:0] dout = 0;
    reg dout_ready = 0;
    wire [7:0] burstcnt, be;
    wire [28:0] addr;
    wire rd, we, pass, fault;
    wire [63:0] din;

    diablo_ddr_probe #(.RETRY_DELAY_CYCLES(3), .MAX_ATTEMPTS(3)) dut (
        .clk(clk), .reset(reset), .ddram_busy(busy), .ddram_dout(dout),
        .ddram_dout_ready(dout_ready), .ddram_burstcnt(burstcnt),
        .ddram_addr(addr), .ddram_rd(rd), .ddram_din(din), .ddram_be(be),
        .ddram_we(we), .pass(pass), .fault(fault)
    );

    integer response_delay = -1;
    integer read_count = 0;
    reg [63:0] memory_word0 = 0;
    reg ack_written = 0;

    always @(posedge clk) begin
        dout_ready <= 0;
        if (rd && !busy && response_delay < 0) begin
            if (addr != 29'h07FC0000 || burstcnt != 1) $fatal(1, "bad read request");
            read_count <= read_count + 1;
            response_delay <= 2;
        end
        if (response_delay > 0) response_delay <= response_delay - 1;
        else if (response_delay == 0) begin
            dout <= memory_word0;
            dout_ready <= 1;
            response_delay <= -1;
            // The first read is deliberately stale. A retry must see this.
            if (read_count == 1) memory_word0 <= 64'hD1AB10F0C0DEC0DE;
        end
        if (we && !busy) begin
            if (addr != 29'h07FC0001 || din != 64'hF9A0BEEFC0DEC0DE || be != 8'hff)
                $fatal(1, "bad acknowledgement write");
            ack_written <= 1;
        end
    end

    integer cycles = 0;
    initial begin
        repeat (3) @(posedge clk);
        reset = 0;
        repeat (4) @(posedge clk);
        busy = 0;
        while (!pass && cycles < 100) begin
            @(posedge clk);
            cycles = cycles + 1;
        end
        if (!pass || fault || !ack_written || read_count < 2)
            $fatal(1, "DDR preflight did not retry and acknowledge correctly");
        $display("diablo_ddr_probe_tb: PASS");
        $finish;
    end
endmodule
