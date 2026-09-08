`timescale 1ns/1ps
module diablo_pcm_player_long_tb;
  localparam [31:0] EPOCH = 32'hd1a61001;
  localparam [28:0] BASE = 29'h07fc0000;
  localparam [28:0] PCM_BASE = BASE + 29'h001ce00;

  reg clk = 0;
  reg reset = 1;
  reg session_valid = 0;
  reg [31:0] session_epoch = EPOCH;
  reg [63:0] arbiter_diagnostic = 0;
  reg ddram_busy = 0;
  reg [63:0] ddram_dout = 0;
  reg ddram_dout_ready = 0;
  wire [7:0] ddram_burstcnt;
  wire [28:0] ddram_addr;
  wire ddram_rd;
  wire [63:0] ddram_din;
  wire [7:0] ddram_be;
  wire ddram_we;
  wire [15:0] audio_l, audio_r;
  wire [31:0] underrun_count, resync_count;
  wire [12:0] queue_depth;
  wire ring_valid;
  reg [31:0] producer_sequence = 480;
  reg [31:0] consumer_sequence = 0;
  reg read_pending = 0;
  reg [28:0] read_address = 0;
  integer cycles = 0;
  integer trace_clear_count = 0;

  diablo_pcm_player #(
    .SAMPLE_DIVISOR(10), .POLL_INTERVAL_CYCLES(30), .PRIME_SAMPLES(16), .ACK_BATCH(32)
  ) dut (.*);

  always #5 clk = ~clk;

  function automatic [63:0] read_word(input [28:0] address);
    begin
      if (address == BASE + 10) read_word = {consumer_sequence, producer_sequence};
      else if (address == BASE + 11) read_word = {32'd4, 32'd32768};
      else if (address == BASE + 13) read_word = {32'd0, EPOCH};
      else if (address >= PCM_BASE && address < PCM_BASE + 29'd240) read_word = 64'd0;
      else read_word = 64'd0;
    end
  endfunction

  always @(posedge clk) begin
    cycles <= cycles + 1;
    ddram_dout_ready <= 0;
    if (read_pending) begin
      ddram_dout <= read_word(read_address);
      ddram_dout_ready <= 1;
      read_pending <= 0;
    end
    if (ddram_rd && !ddram_busy && !read_pending) begin
      read_address <= ddram_addr;
      read_pending <= 1;
    end
    if (ddram_we && !ddram_busy) begin
      if (ddram_addr == BASE + 10 && ddram_be == 8'hf0) begin
        consumer_sequence <= ddram_din[63:32];
      end else if (ddram_addr == BASE + 12 && ddram_be == 8'hff) begin
        if (ddram_din[63:32] !== resync_count || ddram_din[31:0] !== underrun_count)
          $fatal(1, "PCM status counters were not published");
      end else if (ddram_addr == BASE + 13 && ddram_be == 8'hff) begin
        if (ddram_din[31:0] !== EPOCH)
          $fatal(1, "PCM local queue status epoch was not preserved");
      end else if (ddram_addr == BASE + 58 && ddram_be == 8'hff && ddram_din == 0) begin
        trace_clear_count <= trace_clear_count + 1;
      end else begin
        $fatal(1, "PCM write ownership violated");
      end
    end
  end

  initial begin
    repeat (4) @(posedge clk);
    reset <= 0;
    session_valid <= 1;
    wait (consumer_sequence == producer_sequence);
    if (trace_clear_count != 1)
      $fatal(1, "PCM startup did not invalidate the optional underflow commit marker count=%0d", trace_clear_count);
    $display("PCM long queue checks passed consumer=%0d cycles=%0d", consumer_sequence, cycles);
    $finish;
  end

  initial begin
    #5000000;
    $fatal(1, "PCM long queue timeout consumer=%0d queue=%0d underruns=%0d", consumer_sequence, queue_depth, underrun_count);
  end
endmodule
