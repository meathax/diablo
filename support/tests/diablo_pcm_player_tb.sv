`timescale 1ns/1ps
module diablo_pcm_player_tb;
  localparam [31:0] EPOCH = 32'hd1a61001;
  localparam [31:0] NEW_EPOCH = 32'hd1a61002;
  localparam [28:0] BASE = 29'h07fc0000;
  localparam [28:0] PCM_BASE = BASE + 29'h001ce00;

  reg clk = 0;
  reg reset = 1;
  reg session_valid = 0;
  reg [31:0] session_epoch = EPOCH;
  reg [63:0] arbiter_diagnostic = 64'h0123456789abcdef;
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
  integer starvation_edges = 0;
  integer trace_clear_count = 0;
  integer trace_payload_writes = 0;
  integer trace_commit_count = 0;
  reg [63:0] trace_words [0:5];
  reg [31:0] expected_event_cycle = 0;
  reg [31:0] expected_epoch = 0;
  reg [31:0] expected_producer = 0;
  reg [31:0] expected_fetch = 0;
  reg [31:0] expected_consumer = 0;
  reg [31:0] expected_underruns = 0;
  reg [31:0] expected_queue_depth = 0;
  reg [31:0] expected_player_state = 0;
  reg [31:0] expected_resyncs = 0;
  reg transition_request = 0;
  reg transition_injected = 0;
  reg saw_new_epoch_write = 0;
  integer snapshot_index;

  diablo_pcm_player #(
    .SAMPLE_DIVISOR(5), .POLL_INTERVAL_CYCLES(3), .PRIME_SAMPLES(4), .ACK_BATCH(2)
  ) dut (.*);

  always #5 clk = ~clk;

  function automatic [63:0] read_word(input [28:0] address);
    begin
      case (address)
        BASE + 10: read_word = {consumer_sequence, producer_sequence};
        BASE + 11: read_word = {32'd4, 32'd32768};
        BASE + 13: read_word = {32'd0, session_epoch};
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
    if (session_valid && dut.playback_started && dut.sample_tick
        && dut.queue_depth == 0 && dut.producer_has_samples
        && !dut.starvation_active) begin
      starvation_edges = starvation_edges + 1;
      expected_event_cycle = dut.event_cycle;
      expected_epoch = dut.active_epoch;
      expected_producer = dut.producer_sequence;
      expected_fetch = dut.fetch_sequence;
      expected_consumer = dut.published_consumer;
      expected_underruns = dut.underrun_count + 1'b1;
      expected_queue_depth = dut.queue_depth;
      expected_player_state = {21'd0, dut.fetch_pair, dut.status_to_verify, dut.layout_valid,
                               dut.ring_valid, dut.playback_started, dut.playback_running, dut.state};
      expected_resyncs = dut.resync_count;
    end
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
      if (transition_injected && ddram_addr == BASE + 13 && ddram_din[31:0] === EPOCH)
        $fatal(1, "PCM queue status wrote the stale epoch across a session transition");
      if (ddram_addr == BASE + 10 && ddram_be == 8'hf0) begin
        consumer_sequence <= ddram_din[63:32];
        saw_consumer_byte_enable <= 1;
      end else if (ddram_addr == BASE + 12 && ddram_be == 8'hff) begin
        if (ddram_din[63:32] !== resync_count || ddram_din[31:0] !== underrun_count)
          $fatal(1, "PCM status counters were not published");
        saw_status_word <= 1;
      end else if (ddram_addr == BASE + 13 && ddram_be == 8'hff) begin
        if (ddram_din[31:0] !== session_epoch)
          $fatal(1, "PCM local queue status epoch was not preserved");
        if (transition_injected && ddram_din[31:0] === NEW_EPOCH)
          saw_new_epoch_write = 1;
      end else if (ddram_addr >= BASE + 53 && ddram_addr <= BASE + 58 && ddram_be == 8'hff) begin
        // Model the actual six-word reserved-tail memory by decoded address;
        // do not infer validity from the writer state or a sideband signal.
        trace_words[ddram_addr - (BASE + 53)] = ddram_din;
        if (ddram_addr == BASE + 58 && ddram_din == 0) begin
          trace_clear_count = trace_clear_count + 1;
        end else begin
          trace_payload_writes = trace_payload_writes + 1;
          if (ddram_addr == BASE + 58) begin
            trace_commit_count = trace_commit_count + 1;
            if (ddram_din !== {trace_commit_count[31:0], expected_resyncs}
                || trace_words[0] !== {expected_epoch, expected_event_cycle}
                || trace_words[1] !== {expected_fetch, expected_producer}
                || trace_words[2] !== {expected_underruns, expected_consumer}
                || trace_words[3] !== {expected_player_state, expected_queue_depth}
                || trace_words[4] !== arbiter_diagnostic)
              $fatal(1, "PCM underflow snapshot was not coherent commit=%h words=%h/%h/%h/%h/%h",
                     ddram_din, trace_words[0], trace_words[1], trace_words[2], trace_words[3], trace_words[4]);
          end
        end
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

  always @(negedge clk) begin
    if (transition_request && !transition_injected && ddram_we && !ddram_busy
        && ddram_addr == BASE + 13) begin
      // Change the ARM-published epoch while the queue-status write is
      // pending. The FPGA must not commit the old epoch on the next edge.
      session_epoch = NEW_EPOCH;
      transition_injected = 1;
    end
  end

  initial begin
    for (snapshot_index = 0; snapshot_index < 6; snapshot_index = snapshot_index + 1)
      trace_words[snapshot_index] = 0;
    repeat (4) @(posedge clk);
    reset <= 0;
    session_valid <= 1;
    wait (observed == 8);
    if (trace_clear_count != 1 || trace_payload_writes != 0 || trace_commit_count != 0
        || trace_words[5] != 0)
      $fatal(1, "healthy PCM playback did not leave the optional snapshot unavailable clear=%0d payload=%0d commits=%0d marker=%h",
             trace_clear_count, trace_payload_writes, trace_commit_count, trace_words[5]);
    wait (dut.sample_tick && dut.queue_depth == 0);
    repeat (2) @(posedge clk);
    #1;
    if (audio_l != 0 || audio_r != 0)
      $fatal(1, "PCM stopped-producer interval did not output silence");
    // Add frames only after the initial stream drains. This exercises active
    // starvation while keeping producer silence a valid non-error interval.
    producer_sequence <= 12;
    wait (underrun_count != 0);
    wait (trace_commit_count == 1);
    repeat (10) @(posedge clk);
    if (starvation_edges != 1 || trace_clear_count != 2 || trace_payload_writes != 6
        || trace_commit_count != 1 || underrun_count < 2)
      $fatal(1, "PCM starvation event was not one bounded snapshot edges=%0d clear=%0d payload=%0d commits=%0d underruns=%0d",
             starvation_edges, trace_clear_count, trace_payload_writes, trace_commit_count, underrun_count);
    wait (observed == 12);
    producer_sequence <= 16;
    wait (trace_commit_count == 2);
    @(posedge clk);
    if (!ring_valid || consumer_sequence != 16 || !saw_consumer_byte_enable || !saw_status_word)
      $fatal(1, "PCM ring was not validated and acknowledged");
    if (underrun_count == 0 || resync_count != 0)
      $fatal(1, "PCM underrun/recovery counters incorrect underruns=%0d resyncs=%0d", underrun_count, resync_count);
    if (starvation_edges != 2 || trace_clear_count != 3 || trace_payload_writes != 12
        || trace_commit_count != 2)
      $fatal(1, "PCM second starvation episode did not replace snapshot cleanly edges=%0d clear=%0d payload=%0d commits=%0d",
             starvation_edges, trace_clear_count, trace_payload_writes, trace_commit_count);
    transition_request = 1;
    producer_sequence <= 18;
    wait (transition_injected);
    repeat (30) @(posedge clk);
    if (!saw_new_epoch_write)
      $fatal(1, "PCM epoch rebind did not publish the new session epoch");
    // A hardware reset can see the same ARM epoch again. It must explicitly
    // clear the shared commit marker so an ARM reader reports unavailable until
    // another active starvation edge is captured.
    reset <= 1;
    @(posedge clk);
    reset <= 0;
    wait (trace_clear_count == 4);
    if (trace_words[5] != 0 || trace_payload_writes != 12 || trace_commit_count != 2)
      $fatal(1, "same-epoch PCM reset did not invalidate the shared event commit marker=%h payload=%0d commits=%0d",
             trace_words[5], trace_payload_writes, trace_commit_count);
    $display("PCM player checks passed");
    $finish;
  end

  initial begin
    #2000000;
    $fatal(1, "PCM player timeout");
  end
endmodule
