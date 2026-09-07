`timescale 1ns/1ps
// Exercise the imported serializer without changing sys/. The receiver samples
// on rising SCLK and observes the standard one-bit LRCLK-to-MSB offset.
module i2s_interface_tb;
  reg clk = 0;
  always #20.345 clk = ~clk;
  reg reset = 1, ce = 0;
  reg [15:0] left_chan = 16'h96a5, right_chan = 16'h3cc3;
  wire sclk, lrclk, sdata;
  i2s dut(.*);
  integer divider = 8, count = 0;
  always @(negedge clk) begin
    ce = 0;
    if (!reset) begin
      count = count + 1;
      if (count == divider) begin ce = 1; count = 0; end
    end else count = 0;
  end

  realtime last_data = 0, last_lr = 0, last_rise = 0;
  realtime last_fall = 0, delta;
  integer edges = 0, words = 0, bits = 0;
  reg previous_lr = 1, channel = 1;
  reg [15:0] received = 0;
  always @(sdata) begin
    if (!reset && edges > 4 && $realtime-last_rise < 2.5)
      $fatal(1,"I2S data hold below receiver + skew budget");
    last_data = $realtime;
  end
  always @(lrclk) begin
    if (!reset && edges > 4 && $realtime-last_rise < 2.5)
      $fatal(1,"LRCLK hold below receiver + skew budget");
    last_lr = $realtime;
  end
  always @(negedge sclk) begin
    if (!reset && edges > 4) begin
      delta = $realtime-last_rise;
      if (delta < divider*40.69-0.1 || delta > divider*40.69+0.1)
        $fatal(1,"Incorrect SCLK high duration: %f",delta);
    end
    last_fall = $realtime;
  end
  always @(posedge sclk) begin
    if (!reset) begin
      edges = edges + 1;
      if (edges > 4) begin
        if ($realtime-last_data < 2.5 || $realtime-last_lr < 2.5)
          $fatal(1,"I2S setup below receiver + skew budget");
        delta = $realtime-last_fall;
        if (delta < divider*40.69-0.1 || delta > divider*40.69+0.1)
          $fatal(1,"Incorrect SCLK low duration: %f",delta);
      end
      last_rise = $realtime;
      // The sample on an LRCLK transition is the previous word's LSB.
      received = {received[14:0],sdata};
      bits = bits + 1;
      if (lrclk != previous_lr) begin
        if (words > 2) begin
          if (bits != 16) $fatal(1,"I2S word length %0d",bits);
          if (received !== (channel ? right_chan : left_chan))
            $fatal(1,"I2S channel %0d word %h",channel,received);
        end
        words = words + 1;
        bits = 0;
        channel = lrclk;
        previous_lr = lrclk;
      end
    end
  end
  task run_mode(input integer div_value);
    begin
      @(negedge clk); reset = 1; divider = div_value;
      repeat (4) @(negedge clk);
      edges = 0; words = 0; bits = 0; previous_lr = 1; channel = 1;
      reset = 0;
      wait(words == 20);
      $display("PASS I2S divider=%0d: 20 words, channel order and setup/hold",divider);
    end
  endtask
  initial begin
    run_mode(8); // 24.576 MHz / (8*2*32) = 48 kHz
    run_mode(4); // 96 kHz
    $finish;
  end
  initial begin #2000000; $fatal(1,"I2S timeout"); end
endmodule
