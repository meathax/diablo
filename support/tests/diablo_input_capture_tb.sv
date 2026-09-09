`timescale 1ns/1ps
module diablo_input_capture_tb;
  localparam [28:0] SHARED_BASE_WORD = 29'h07fc0000;
  localparam [28:0] INPUT_CONTROL_WORD = SHARED_BASE_WORD + 29'd6;
  localparam [28:0] INPUT_LAYOUT_WORD = SHARED_BASE_WORD + 29'd7;
  localparam [28:0] INPUT_DROPPED_WORD = SHARED_BASE_WORD + 29'd8;
  localparam [28:0] INPUT_EPOCH_WORD = SHARED_BASE_WORD + 29'd9;
  localparam [28:0] INPUT_DATA_BASE_WORD = SHARED_BASE_WORD + (32'h000e5000 >> 3);

  reg clk = 0, reset = 1, session_valid = 1;
  reg [31:0] session_epoch = 32'd1;
  reg [31:0] joystick_0 = 0;
  reg [15:0] joystick_l_analog_0 = 0, joystick_r_analog_0 = 0;
  reg [10:0] ps2_key = 0;
  reg [24:0] ps2_mouse = 0;
  reg [15:0] ps2_mouse_ext = 0;
  reg [1:0] buttons = 0;
  reg osd_status = 0;

  wire ddram_busy = 1'b0;
  reg [63:0] ddram_dout = 0;
  reg ddram_dout_ready = 0;
  wire [7:0] ddram_burstcnt;
  wire [28:0] ddram_addr;
  wire ddram_rd;
  wire [63:0] ddram_din;
  wire [7:0] ddram_be;
  wire ddram_we;
  wire ring_valid;
  wire [31:0] overflow_count;

  reg [31:0] producer_model = 0;
  reg [31:0] consumer_model = 0;
  reg [63:0] dropped_model = 0;
  reg [63:0] ring [0:1023];
  integer i;

  diablo_input_capture dut (.*);
  always #5 clk = ~clk;

  function automatic [63:0] model_read(input [28:0] addr);
    integer index;
    begin
      if (addr == INPUT_CONTROL_WORD) model_read = {consumer_model, producer_model};
      else if (addr == INPUT_LAYOUT_WORD) model_read = {32'd32, 32'd256};
      else if (addr == INPUT_DROPPED_WORD) model_read = dropped_model;
      else if (addr == INPUT_EPOCH_WORD) model_read = {32'd0, session_epoch};
      else if (addr >= INPUT_DATA_BASE_WORD && addr < INPUT_DATA_BASE_WORD + 1024) begin
        index = addr - INPUT_DATA_BASE_WORD;
        model_read = ring[index];
      end else model_read = 64'd0;
    end
  endfunction

  always @(posedge clk) begin
    ddram_dout_ready <= 1'b0;
    if (ddram_rd) begin
      ddram_dout <= model_read(ddram_addr);
      ddram_dout_ready <= 1'b1;
    end
    if (ddram_we && !ddram_busy) begin
      if (ddram_addr == INPUT_CONTROL_WORD) begin
        if (ddram_be[3:0]) producer_model <= ddram_din[31:0];
      end else if (ddram_addr == INPUT_DROPPED_WORD) begin
        dropped_model <= ddram_din;
      end else if (ddram_addr >= INPUT_DATA_BASE_WORD
                && ddram_addr < INPUT_DATA_BASE_WORD + 1024) begin
        ring[ddram_addr - INPUT_DATA_BASE_WORD] <= ddram_din;
      end
    end
  end

  task automatic wait_producer(input [31:0] expected);
    integer timeout;
    begin
      timeout = 0;
      while (producer_model != expected && timeout < 10000) begin
        @(posedge clk);
        timeout = timeout + 1;
      end
      if (producer_model != expected) $fatal(1, "input producer timeout expected=%0d actual=%0d", expected, producer_model);
    end
  endtask

  task automatic wait_ring_valid;
    integer timeout;
    begin
      timeout = 0;
      while (!ring_valid && timeout < 10000) begin
        @(posedge clk);
        timeout = timeout + 1;
      end
      if (!ring_valid) $fatal(1, "input ring did not attach");
    end
  endtask

  initial begin
    for (i = 0; i < 1024; i = i + 1) ring[i] = 0;
    repeat (3) @(posedge clk);
    reset = 0;
    wait_ring_valid();

    ps2_key = {1'b1, 1'b1, 1'b0, 8'h1c};
    wait_producer(32'd1);
    if (ring[1][31:0] != 32'd1 || ring[1][63:32] != {23'd0, 1'b0, 8'h1c}
        || ring[2][31:0] != 32'd1 || ring[2][63:32] != 0)
      $fatal(1, "keyboard event packing failed");

    // Check both ninth-bit signs without toggling the packet-ready bit.
    ps2_mouse = 0;
    ps2_mouse[15:8] = 8'h80;
    ps2_mouse[23:16] = 8'h80;
    #1;
    if (dut.mouse_dx != 32'd128 || dut.mouse_dy != 32'hffffff80)
      $fatal(1, "positive PS2 ninth-bit motion decode failed");
    ps2_mouse[4] = 1;
    ps2_mouse[5] = 1;
    #1;
    if (dut.mouse_dx != 32'hffffff80 || dut.mouse_dy != 32'd128)
      $fatal(1, "negative PS2 ninth-bit motion decode failed");
    ps2_mouse = 0;
    ps2_mouse[24] = 1'b1;
    ps2_mouse[2:0] = 3'b101;
    ps2_mouse[15:8] = 8'hfe;
    ps2_mouse[23:16] = 8'h03;
    ps2_mouse_ext = 16'h0004;
    wait_producer(32'd2);
    if (ring[5][31:0] != 32'd2 || ring[5][63:32] != {21'd0, 3'b101, 8'h04}
        || ring[6][31:0] != 32'd254 || ring[6][63:32] != 32'hfffffffd)
      $fatal(1, "mouse event packing failed");

    joystick_0 = 32'h00000081;
    joystick_l_analog_0 = 16'hff80;
    joystick_r_analog_0 = 16'h007f;
    wait_producer(32'd3);
    if (ring[9][31:0] != 32'd3 || ring[10][31:0] != 32'hffffff80
        || ring[10][63:32] != 32'h0000007f || ring[11][31:0] != 32'h00000081)
      $fatal(1, "joystick event packing failed");

    // Controller-button changes are input payload and must not change focus.
    buttons = 2'b01;
    repeat (100) @(posedge clk);
    if (producer_model != 32'd3)
      $fatal(1, "button change was incorrectly published as a focus event");

    // MiSTer's OSD status is the focus source: open loses focus, close gains it.
    osd_status = 1'b1;
    wait_producer(32'd4);
    if (ring[13][31:0] != 32'd4 || ring[14][31:0] != 32'd1)
      $fatal(1, "focus event packing failed");

    osd_status = 1'b0;
    wait_producer(32'd5);
    if (ring[17][31:0] != 32'd4 || ring[18][31:0] != 32'd0)
      $fatal(1, "OSD-close focus event packing failed");

    // A new session with a full ring must drop the edge and report overflow
    // without corrupting the producer cursor.
    reset = 1;
    session_epoch = 32'd2;
    producer_model = 32'd256;
    consumer_model = 0;
    ps2_key[10] = 1'b0;
    repeat (3) @(posedge clk);
    reset = 0;
    wait_ring_valid();
    ps2_key[10] = 1'b1;
    begin : wait_overflow
      integer timeout;
      timeout = 0;
      while (overflow_count == 0 && timeout < 10000) begin
        @(posedge clk);
        timeout = timeout + 1;
      end
    end
    if (overflow_count == 0 || producer_model != 32'd256)
      $fatal(1, "full input ring did not recover by dropping event");
    begin : wait_dropped_publication
      integer timeout;
      timeout = 0;
      while (dropped_model == 0 && timeout < 10000) begin
        @(posedge clk);
        timeout = timeout + 1;
      end
    end
    if (dropped_model != 64'd1)
      $fatal(1, "input overflow counter was not published to the ABI");

    $display("input capture checks passed events=5 overflow=%0d dropped=%0d", overflow_count, dropped_model);
    $finish;
  end

  initial begin #500000; $fatal(1, "input capture timeout"); end
endmodule
