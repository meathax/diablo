`timescale 1ns/1ps
module diablo_pcm_player_tb;
  localparam [31:0] EPOCH = 32'hd1a61001;
  localparam [28:0] BASE = 29'h07fc0000;
  localparam [28:0] PCM_BASE = BASE + 29'h001ce00;

  reg clk = 0;
  reg reset = 1;
  reg session_valid = 0;
  reg [31:0] session_epoch = EPOCH;
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
  reg [31:0] producer_sequence = 8;
  reg [31:0] consumer_sequence = 0;
  reg read_pending = 0;
  reg [28:0] read_address = 0;
  integer observed = 0;
  reg [15:0] previous_left = 0;
  reg saw_consumer_byte_enable = 0;
  reg saw_status_word = 0;

  diablo_pcm_player #(
    .SAMPLE_DIVISOR(5), .POLL_INTERVAL_CYCLES(3), .PRIME_SAMPLES(4), .ACK_BATCH(2)
  ) dut (.*);

  always #5 clk = ~clk;

  function automatic [63:0] read_word(input [28:0] address);
    begin
      case (address)
        BASE + 10: read_word = {consumer_sequence, producer_sequence};
        BASE + 11: read_word = {32'd4, 32'd32768};
        BASE + 13: read_word = {32'd0, EPOCH};
        PCM_BASE + 0: read_word = {16'h2001, 16'h1001, 16'h2000, 16'h1000};
        PCM_BASE + 1: read_word = {16'h2003, 16'h1003, 16'h2002, 16'h1002};
        PCM_BASE + 2: read_word = {16'h2005, 16'h1005, 16'h2004, 16'h1004};
        PCM_BASE + 3: read_word = {16'h2007, 16'h1007, 16'h2006, 16'h1006};
        PCM_BASE + 4: read_word = {16'h2009, 16'h1009, 16'h2008, 16'h1008};
        PCM_BASE + 5: read_word = {16'h200b, 16'h100b, 16'h200a, 16'h100a};
        default: read_word = 0;
      endcase
    end
  endfunction

  always @(posedge clk) begin
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
        saw_consumer_byte_enable <= 1;
      end else if (ddram_addr == BASE + 12 && ddram_be == 8'hff) begin
        if (ddram_din[63:32] !== resync_count || ddram_din[31:0] !== underrun_count)
          $fatal(1, "PCM status counters were not published");
        saw_status_word <= 1;
      end else if (ddram_addr == BASE + 13 && ddram_be == 8'hff) begin
        if (ddram_din[31:0] !== EPOCH)
          $fatal(1, "PCM local queue status epoch was not preserved");
      end else begin
        $fatal(1, "PCM write ownership violated");
      end
    end

    if (audio_l != 0 && audio_l != previous_left) begin
      if (audio_l !== 16'h1000 + observed || audio_r !== 16'h2000 + observed)
        $fatal(1, "PCM channel/order mismatch sample=%0d left=%h right=%h", observed, audio_l, audio_r);
      observed <= observed + 1;
      previous_left <= audio_l;
    end
  end

  initial begin
    repeat (4) @(posedge clk);
    reset <= 0;
    session_valid <= 1;
    wait (observed == 8);
    wait (underrun_count != 0);
    @(posedge clk);
    if (audio_l != 0 || audio_r != 0)
      $fatal(1, "PCM underrun did not output silence");
    producer_sequence <= 12;
    wait (observed == 12);
    @(posedge clk);
    if (!ring_valid || consumer_sequence != 12 || !saw_consumer_byte_enable || !saw_status_word)
      $fatal(1, "PCM ring was not validated and acknowledged");
    if (underrun_count == 0 || resync_count != 0)
      $fatal(1, "PCM underrun/recovery counters incorrect underruns=%0d resyncs=%0d", underrun_count, resync_count);
    $display("PCM player checks passed");
    $finish;
  end

  initial begin
    #2000000;
    $fatal(1, "PCM player timeout");
  end
endmodule
