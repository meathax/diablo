`timescale 1ns/1ps
module diablo_transport_ddram_arbiter_tb;
  reg clk = 0, reset = 1, session_valid = 0;
  reg [7:0] control_burstcnt = 1, frame_burstcnt = 1, audio_burstcnt = 1, input_burstcnt = 1, command_burstcnt = 1;
  reg [28:0] control_addr = 29'h11, frame_addr = 29'h22, audio_addr = 29'h33, input_addr = 29'h44, command_addr = 29'h55;
  reg control_rd = 0, frame_rd = 0, audio_rd = 0, input_rd = 0, command_rd = 0;
  reg [63:0] control_din = 64'h11, frame_din = 64'h22, audio_din = 64'h33, input_din = 64'h44, command_din = 64'h55;
  reg [7:0] control_be = 8'hff, frame_be = 8'h0f, audio_be = 8'hf0, input_be = 8'hff, command_be = 8'hff;
  reg control_we = 0, frame_we = 0, audio_we = 0, input_we = 0, command_we = 0;
  wire control_busy; wire [63:0] control_dout; wire control_dout_ready;
  wire frame_busy; wire [63:0] frame_dout; wire frame_dout_ready;
  wire audio_busy; wire [63:0] audio_dout; wire audio_dout_ready;
  wire input_busy; wire [63:0] input_dout; wire input_dout_ready;
  wire command_busy; wire [63:0] command_dout; wire command_dout_ready;
  reg ddram_busy = 0; reg [63:0] ddram_dout = 64'h0123456789abcdef; reg ddram_dout_ready = 0;
  wire [7:0] ddram_burstcnt; wire [28:0] ddram_addr; wire ddram_rd;
  wire [63:0] ddram_din; wire [7:0] ddram_be; wire ddram_we;
  wire fault; wire [63:0] diagnostic;

  diablo_transport_ddram_arbiter #(.READ_RESPONSE_TIMEOUT_CYCLES(4), .BUSY_TIMEOUT_CYCLES(4)) dut (.*);
  always #5 clk = ~clk;

  initial begin
    @(posedge clk);
    #1;
    reset = 0;
    #1;
    control_rd = 1;
    #1;
    if (!ddram_rd || ddram_addr != control_addr || control_busy != 0)
      $fatal(1, "control reader did not own pre-attach DDR");
    @(posedge clk);
    #1;
    control_rd = 0;
    ddram_dout_ready = 1;
    #1;
    if (!control_dout_ready || control_dout != ddram_dout || !frame_busy || !audio_busy)
      $fatal(1, "control response routing failed");
    @(posedge clk);
    #1;
    ddram_dout_ready = 0;
    session_valid = 1;

    frame_rd = 1;
    audio_rd = 1;
    input_rd = 1;
    command_rd = 1;
    ddram_busy = 1;
    #1;
    if (!ddram_rd || ddram_addr != audio_addr || audio_busy != 1 || input_busy != 1 || frame_busy != 1
        || diagnostic[2:0] != 3'd2 || !diagnostic[55])
      $fatal(1, "DDR backpressure was not propagated to every pending client diag=%h", diagnostic);
    @(posedge clk);
    #1;
    ddram_busy = 0;
    #1;
    if (audio_busy != 0 || input_busy != 1 || frame_busy != 1)
      $fatal(1, "DDR owner did not resume after backpressure cleared");
    #1;
    if (!ddram_rd || ddram_addr != audio_addr || !frame_busy || audio_busy != 0)
      $fatal(1, "audio priority was not applied");
    @(posedge clk);
    #1;
    audio_rd = 0;
    #1;
    if (ddram_rd || !frame_busy || audio_busy != 0 || diagnostic[2:0] != 3'd2
        || !diagnostic[3] || diagnostic[7:5] != 3'd2)
      $fatal(1, "audio arbitration snapshot was not coherent diag=%h rd=%b frame_busy=%b audio_busy=%b fault=%b pending=%b", diagnostic, ddram_rd, frame_busy, audio_busy, fault, dut.read_pending);
    ddram_dout_ready = 1;
    #1;
    if (!audio_dout_ready || frame_dout_ready || audio_dout != ddram_dout)
      $fatal(1, "outstanding response reached wrong client");
    @(posedge clk);
    #1;
    ddram_dout_ready = 0;
    audio_rd = 0;
    input_rd = 1;
    #1;
    if (!ddram_rd || ddram_addr != input_addr || input_busy != 0 || !frame_busy)
      $fatal(1, "input priority was not applied");
    @(posedge clk);
    #1;
    input_rd = 0;
    command_rd = 0;
    ddram_dout_ready = 1;
    #1;
    if (!input_dout_ready || frame_dout_ready || input_dout != ddram_dout)
      $fatal(1, "input response routing failed");
    @(posedge clk);
    #1;
    ddram_dout_ready = 0;
    frame_rd = 0;
    command_rd = 1;
    #1;
    if (!ddram_rd || ddram_addr != command_addr || command_busy != 0 || frame_busy != 1)
      $fatal(1, "command owner did not resume after input response");
    @(posedge clk);
    #1;
    command_rd = 0;
    ddram_dout_ready = 1;
    #1;
    if (!command_dout_ready || frame_dout_ready || command_dout != ddram_dout)
      $fatal(1, "command response routing failed");
    @(posedge clk);
    #1;
    ddram_dout_ready = 0;
    // Frame metadata/palette traffic must outrank command rendering so a
    // command batch cannot delay the next vblank handoff.
    frame_rd = 1;
    command_rd = 1;
    #1;
    if (!ddram_rd || ddram_addr != frame_addr || frame_busy != 0 || command_busy != 1)
      $fatal(1, "frame scanout did not outrank command rendering");
    @(posedge clk);
    #1;
    frame_rd = 0;
    command_rd = 0;
    ddram_dout_ready = 1;
    #1;
    if (!frame_dout_ready || command_dout_ready || frame_dout != ddram_dout)
      $fatal(1, "frame response was not routed ahead of command rendering");
    @(posedge clk);
    #1;
    ddram_dout_ready = 0;

    // Reset while an input read is outstanding. No stale response may leak
    // to the input client, and the arbiter must recover for the next request.
    input_rd = 1;
    #1;
    if (!ddram_rd || ddram_addr != input_addr)
      $fatal(1, "input read was not accepted before reset test");
    @(posedge clk);
    #1;
    reset = 1;
    ddram_dout_ready = 1;
    #1;
    if (input_dout_ready || frame_dout_ready || audio_dout_ready || control_dout_ready)
      $fatal(1, "reset leaked an outstanding DDR response");
    @(posedge clk);
    #1;
    reset = 0;
    ddram_dout_ready = 0;
    input_rd = 0;


    audio_we = 1;
    #1;
    if (!ddram_we || ddram_addr != audio_addr || ddram_be != 8'hf0 || ddram_din != audio_din)
      $fatal(1, "audio acknowledgement write was not forwarded");
    audio_we = 0;

    // A write burst retains its owner and remaining-beat count. The diagnostic
    // is captured by PCM only on an event, so assert the raw packed fields here.
    command_burstcnt = 3;
    command_we = 1;
    #1;
    if (!ddram_we || ddram_addr != command_addr || diagnostic[2:0] != 3'd4)
      $fatal(1, "command burst did not start with command selected diag=%h", diagnostic);
    @(posedge clk);
    #1;
    if (!diagnostic[4] || diagnostic[10:8] != 3'd4 || diagnostic[18:11] != 8'd2)
      $fatal(1, "command burst diagnostic did not retain first accepted beat diag=%h", diagnostic);
    @(posedge clk);
    #1;
    if (!diagnostic[4] || diagnostic[18:11] != 8'd1)
      $fatal(1, "command burst diagnostic did not decrement remaining beats diag=%h", diagnostic);
    @(posedge clk);
    #1;
    if (diagnostic[4] || diagnostic[18:11] != 0)
      $fatal(1, "command burst diagnostic did not release after final beat diag=%h", diagnostic);
    command_we = 0;
    command_burstcnt = 1;

    // Session monitoring must progress even under continuous audio traffic.
    // Otherwise a new ARM epoch can remain invisible to every FPGA client.
    @(negedge clk);
    audio_we = 1;
    control_rd = 1;
    #1;
    if (!ddram_rd || ddram_addr != control_addr || control_busy || !audio_busy)
      $fatal(1, "session monitor starved by continuous audio traffic");
    @(posedge clk);
    #1;
    control_rd = 0;
    if (ddram_we || !audio_busy)
      $fatal(1, "audio interrupted session monitor read");
    ddram_dout_ready = 1;
    #1;
    if (!control_dout_ready || audio_dout_ready)
      $fatal(1, "session monitor response reached wrong client");
    @(posedge clk);
    #1;
    ddram_dout_ready = 0;
    if (!ddram_we || ddram_addr != audio_addr || audio_busy)
      $fatal(1, "audio did not resume after session monitor response");
    audio_we = 0;

    // A missing reply must fail closed.  A very late reply may only reach the
    // client that issued the timed-out read; no later transaction is issued.
    control_rd = 1;
    #1;
    if (!ddram_rd || ddram_addr != control_addr)
      $fatal(1, "control read was not accepted before response timeout");
    @(posedge clk);
    #1;
    control_rd = 0;
    repeat (4) @(posedge clk);
    #1;
    if (!fault || ddram_rd || ddram_we || !control_busy || !frame_busy || !audio_busy || !input_busy || !command_busy)
      $fatal(1, "missing response did not produce a fail-stop DDR fault");
    ddram_dout_ready = 1;
    #1;
    if (!control_dout_ready || frame_dout_ready || audio_dout_ready || input_dout_ready || command_dout_ready)
      $fatal(1, "late response was not confined to its original owner");
    @(posedge clk);
    #1;
    ddram_dout_ready = 0;

    // Reset is the explicit recovery boundary.  A stuck ddram_busy before an
    // acceptance must become visible without manufacturing a response.
    reset = 1;
    @(posedge clk);
    #1;
    reset = 0;
    session_valid = 1;
    command_we = 1;
    ddram_busy = 1;
    repeat (4) @(posedge clk);
    #1;
    if (!fault || ddram_we || ddram_rd || !command_busy)
      $fatal(1, "stuck DDR busy did not produce a fail-stop fault");
    command_we = 0;
    ddram_busy = 0;
    $display("DDR arbiter checks passed");
    $finish;
  end

  initial begin #100000; $fatal(1, "DDR arbiter timeout"); end
endmodule
