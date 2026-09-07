`timescale 1ns/1ps
// One bounded-latency shared DDR model behind every production transport client.
// It deliberately does not replace a physical combined-load qualification; it
// proves that the actual client/arbiter ports retain response ownership under
// contended, delayed traffic before that board work starts.
module diablo_transport_integrated_tb;
  `include "diablo_transport_abi.svh"
  localparam [28:0] BASE = 29'h07fc0000;
  localparam [31:0] EPOCH = 32'h51a7e001;
  localparam [28:0] PCM_BASE = BASE + 29'h001ce00;
  localparam [28:0] INPUT_BASE = BASE + (32'h000e5000 >> 3);
  localparam [28:0] RECORD_BASE = BASE + 29'h20e00;

  reg clk = 0, reset = 1;
  always #5 clk = ~clk;
  reg vblank = 0, fb_pal_clk = 0;
  always #7 fb_pal_clk = ~fb_pal_clk;
  wire attached, control_fault; wire [31:0] attached_epoch;
  wire session_valid = attached; wire [31:0] session_epoch = attached_epoch;
  reg [31:0] joystick_0 = 0; reg [15:0] joystick_l_analog_0 = 0, joystick_r_analog_0 = 0;
  reg [10:0] ps2_key = 0; reg [24:0] ps2_mouse = 0; reg [15:0] ps2_mouse_ext = 0;
  reg [1:0] buttons = 0; reg osd_status = 0;

  // Five client ports into the actual priority/ownership arbiter.
  wire [7:0] cb; wire [28:0] ca; wire cr; wire [63:0] cdin; wire [7:0] cbe; wire cwe, cbusy; wire [63:0] cdout; wire cready;
  wire [7:0] fb; wire [28:0] fa; wire fr; wire [63:0] fdin; wire [7:0] fbe; wire fwe, fbusy; wire [63:0] fdout; wire fready;
  wire [7:0] ab; wire [28:0] aa; wire ar; wire [63:0] adin; wire [7:0] abe; wire awe, abusy; wire [63:0] adout; wire aready;
  wire [7:0] ib; wire [28:0] ia; wire ir; wire [63:0] idin; wire [7:0] ibe; wire iwe, ibusy; wire [63:0] idout; wire iready;
  wire [7:0] mb; wire [28:0] ma; wire mr; wire [63:0] mdin; wire [7:0] mbe; wire mwe, mbusy; wire [63:0] mdout; wire mready;
  wire [7:0] db; wire [28:0] da; wire dr; wire [63:0] ddin; wire [7:0] dbe; wire dwe;
  wire ddram_fault;
  reg dbusy = 0; reg [63:0] ddout = 0; reg ddout_ready = 0;

  wire framebuffer_valid; wire [31:0] framebuffer_base; wire framebuffer_blank;
  wire [7:0] fb_pal_addr; wire [23:0] fb_pal_dout; wire fb_pal_wr;
  wire [15:0] audio_l, audio_r; wire [31:0] underruns, resyncs; wire [10:0] pcm_depth; wire pcm_valid;
  wire input_valid; wire [31:0] input_overflows;
  wire command_valid, command_fault; wire [31:0] commands_executed, commands_rejected; wire [63:0] last_fence;

  diablo_transport_control_reader #(.RETRY_DELAY_CYCLES(3), .RECHECK_DELAY_CYCLES(6)) control (
    .clk(clk), .reset(reset), .ddram_busy(cbusy), .ddram_dout(cdout), .ddram_dout_ready(cready),
    .ddram_burstcnt(cb), .ddram_addr(ca), .ddram_rd(cr), .ddram_din(cdin), .ddram_be(cbe), .ddram_we(cwe),
    .attached(attached), .fault(control_fault), .attached_epoch(attached_epoch));
  diablo_framebuffer_scanout frame (
    .clk(clk), .reset(reset), .session_valid(session_valid), .session_epoch(session_epoch), .vblank(vblank),
    .ddram_busy(fbusy), .ddram_dout(fdout), .ddram_dout_ready(fready), .ddram_burstcnt(fb), .ddram_addr(fa),
    .ddram_rd(fr), .ddram_din(fdin), .ddram_be(fbe), .ddram_we(fwe), .framebuffer_valid(framebuffer_valid),
    .framebuffer_base(framebuffer_base), .framebuffer_blank(framebuffer_blank), .fb_pal_clk(fb_pal_clk),
    .fb_pal_addr(fb_pal_addr), .fb_pal_dout(fb_pal_dout), .fb_pal_wr(fb_pal_wr));
  diablo_pcm_player #(.SAMPLE_DIVISOR(4), .POLL_INTERVAL_CYCLES(3), .PRIME_SAMPLES(2), .ACK_BATCH(2)) audio (
    .clk(clk), .reset(reset), .session_valid(session_valid), .session_epoch(session_epoch), .ddram_busy(abusy),
    .ddram_dout(adout), .ddram_dout_ready(aready), .ddram_burstcnt(ab), .ddram_addr(aa), .ddram_rd(ar),
    .ddram_din(adin), .ddram_be(abe), .ddram_we(awe), .audio_l(audio_l), .audio_r(audio_r),
    .underrun_count(underruns), .resync_count(resyncs), .queue_depth(pcm_depth), .ring_valid(pcm_valid));
  diablo_input_capture input_capture (
    .clk(clk), .reset(reset), .session_valid(session_valid), .session_epoch(session_epoch), .joystick_0(joystick_0),
    .joystick_l_analog_0(joystick_l_analog_0), .joystick_r_analog_0(joystick_r_analog_0), .ps2_key(ps2_key),
    .ps2_mouse(ps2_mouse), .ps2_mouse_ext(ps2_mouse_ext), .buttons(buttons), .osd_status(osd_status),
    .ddram_busy(ibusy), .ddram_dout(idout), .ddram_dout_ready(iready), .ddram_burstcnt(ib), .ddram_addr(ia),
    .ddram_rd(ir), .ddram_din(idin), .ddram_be(ibe), .ddram_we(iwe), .ring_valid(input_valid), .overflow_count(input_overflows));
  diablo_command_consumer #(.POLL_INTERVAL_CYCLES(2)) command (
    .clk(clk), .reset(reset), .session_valid(session_valid), .session_epoch(session_epoch), .target_pixel_base(32'h3fe01000),
    .ddram_busy(mbusy), .ddram_dout(mdout), .ddram_dout_ready(mready), .ddram_burstcnt(mb), .ddram_addr(ma),
    .ddram_rd(mr), .ddram_din(mdin), .ddram_be(mbe), .ddram_we(mwe), .ring_valid(command_valid), .fault(command_fault),
    .commands_executed(commands_executed), .commands_rejected(commands_rejected), .last_fence(last_fence));
  diablo_transport_ddram_arbiter arbiter (
    .clk(clk), .reset(reset), .session_valid(session_valid),
    .control_burstcnt(cb), .control_addr(ca), .control_rd(cr), .control_din(cdin), .control_be(cbe), .control_we(cwe), .control_busy(cbusy), .control_dout(cdout), .control_dout_ready(cready),
    .frame_burstcnt(fb), .frame_addr(fa), .frame_rd(fr), .frame_din(fdin), .frame_be(fbe), .frame_we(fwe), .frame_busy(fbusy), .frame_dout(fdout), .frame_dout_ready(fready),
    .audio_burstcnt(ab), .audio_addr(aa), .audio_rd(ar), .audio_din(adin), .audio_be(abe), .audio_we(awe), .audio_busy(abusy), .audio_dout(adout), .audio_dout_ready(aready),
    .input_burstcnt(ib), .input_addr(ia), .input_rd(ir), .input_din(idin), .input_be(ibe), .input_we(iwe), .input_busy(ibusy), .input_dout(idout), .input_dout_ready(iready),
    .command_burstcnt(mb), .command_addr(ma), .command_rd(mr), .command_din(mdin), .command_be(mbe), .command_we(mwe), .command_busy(mbusy), .command_dout(mdout), .command_dout_ready(mready),
    .ddram_busy(dbusy), .ddram_dout(ddout), .ddram_dout_ready(ddout_ready), .ddram_burstcnt(db), .ddram_addr(da), .ddram_rd(dr), .ddram_din(ddin), .ddram_be(dbe), .ddram_we(dwe), .fault(ddram_fault));

  reg [31:0] frame_state [0:2]; reg [31:0] frame_generation [0:2]; reg [63:0] frame_id [0:2];
  reg [31:0] input_producer = 0, input_consumer = 0; reg [63:0] input_dropped = 0;
  reg [31:0] pcm_producer = 8, pcm_consumer = 0;
  reg [31:0] record_producer = 3, record_consumer = 0; reg [31:0] payload_producer = 0, payload_consumer = 0;
  reg [63:0] observed_fence = 0; reg [63:0] record_words [0:11];
  reg pending = 0; reg [28:0] pending_addr = 0; reg [2:0] delay = 0; reg [15:0] lfsr = 16'h9e37;
  integer reads = 0, responses = 0, writes = 0, vblank_writes = 0, input_writes = 0, pcm_writes = 0, command_pixel_writes = 0;
  integer i;

  function automatic [63:0] read_word(input [28:0] addr);
    begin
      if (addr == BASE + 0) read_word = DIABLO_TRANSPORT_MAGIC_LE64;
      else if (addr == BASE + 1) read_word = {DIABLO_TRANSPORT_CONTROL_BYTES, DIABLO_TRANSPORT_ABI_MINOR, DIABLO_TRANSPORT_ABI_MAJOR};
      else if (addr == BASE + 2) read_word = {DIABLO_TRANSPORT_LITTLE_ENDIAN_TAG, DIABLO_TRANSPORT_SHARED_BYTES};
      else if (addr == BASE + 3) read_word = {EPOCH, 32'd0};
      else if (addr == BASE + 4) read_word = {DIABLO_COMPONENT_READY, DIABLO_COMPONENT_READY};
      else if (addr == BASE + 6) read_word = {input_consumer, input_producer};
      else if (addr == BASE + 7) read_word = {32'd32, 32'd256};
      else if (addr == BASE + 8) read_word = input_dropped;
      else if (addr == BASE + 9) read_word = {32'd0, EPOCH};
      else if (addr == BASE + 10) read_word = {pcm_consumer, pcm_producer};
      else if (addr == BASE + 11) read_word = {32'd4, 32'd32768};
      else if (addr == BASE + 13) read_word = {32'd0, EPOCH};
      else if (addr == BASE + 14) read_word = {record_consumer, record_producer};
      else if (addr == BASE + 15) read_word = {32'd32, 32'd2048};
      else if (addr == BASE + 17) read_word = {32'd0, EPOCH};
      else if (addr == BASE + 18) read_word = {payload_consumer, payload_producer};
      else if (addr == BASE + 19) read_word = {32'd1, 32'd196608};
      else if (addr == BASE + 21) read_word = {32'd0, EPOCH};
      else if (addr >= BASE + 22 && addr < BASE + 46) begin
        i = (addr - (BASE + 22)) / 8;
        case ((addr - (BASE + 22)) % 8)
          0: read_word = {frame_generation[i], frame_state[i]};
          1: read_word = frame_id[i];
          3: read_word = {DIABLO_TRANSPORT_FRAME_PIXEL_BYTES, diablo_transport_frame_offset(i)};
          4: read_word = {DIABLO_TRANSPORT_PALETTE_BYTES, diablo_transport_palette_offset(i)};
          5: read_word = {32'd0, EPOCH};
          default: read_word = 0;
        endcase
      end else if (addr >= PCM_BASE && addr < PCM_BASE + 8)
        read_word = {16'h2001,16'h1001,16'h2000,16'h1000};
      else if (addr >= INPUT_BASE && addr < INPUT_BASE + 1024) read_word = 0;
      else if (addr >= RECORD_BASE && addr < RECORD_BASE + 12) read_word = record_words[addr-RECORD_BASE];
      else if ((addr >= BASE + 29'd38912 && addr < BASE + 29'd39008) || (addr >= BASE + 29'd77824 && addr < BASE + 29'd77920))
        read_word = 64'h0706050403020100;
      else read_word = 0;
    end
  endfunction

  task automatic apply_write(input [28:0] addr, input [63:0] data, input [7:0] be);
    integer slot;
    begin
      writes = writes + 1;
      if (addr == BASE + 6 && be[3:0]) begin input_producer = data[31:0]; input_writes = input_writes + 1; end
      else if (addr == BASE + 8) input_dropped = data;
      else if (addr == BASE + 10 && be[7:4]) begin pcm_consumer = data[63:32]; pcm_writes = pcm_writes + 1; end
      else if (addr == BASE + 14 && be[7:4]) record_consumer = data[63:32];
      else if (addr == BASE + 18 && be[7:4]) payload_consumer = data[63:32];
      else if (addr == BASE + 47) observed_fence = data;
      else if (addr >= BASE + 29'd512 && addr < BASE + 29'd512 + 29'd116736) command_pixel_writes = command_pixel_writes + 1;
      else if (addr >= BASE + 22 && addr < BASE + 46) begin
        slot = (addr - (BASE + 22)) / 8;
        if (((addr - (BASE + 22)) % 8) == 0 && be[3:0]) begin frame_state[slot] = data[31:0]; vblank_writes = vblank_writes + 1; end
      end
    end
  endtask

  always @(posedge clk) begin
    ddout_ready <= 0;
    lfsr <= {lfsr[14:0], lfsr[15]^lfsr[13]^lfsr[12]^lfsr[10]};
    if (pending) begin
      if (delay == 0) begin ddout <= read_word(pending_addr); ddout_ready <= 1; pending <= 0; dbusy <= 0; responses = responses + 1; end
      else begin delay <= delay - 1'b1; dbusy <= 1; end
    end else begin
      dbusy <= 0;
      if ((dr || dwe) && !dbusy) begin
        if (dr) begin pending <= 1; pending_addr <= da; delay <= {1'b0,lfsr[1:0]} + 1'b1; dbusy <= 1; reads = reads + 1; end
        if (dwe) apply_write(da, ddin, dbe);
      end
    end
  end

  task automatic pulse_vblank;
    begin @(posedge clk); vblank <= 1; @(posedge clk); vblank <= 0; end
  endtask
  initial begin
    for (i=0;i<3;i=i+1) begin frame_state[i]=DIABLO_FRAME_FREE; frame_generation[i]=EPOCH; frame_id[i]=0; end
    record_words[0] = {32'h0000007a,32'h00000001}; record_words[1] = {32'd5,32'd4}; record_words[2] = {32'd2,32'd3}; record_words[3] = 0;
    record_words[4] = {32'd0,32'h00000002}; record_words[5] = {32'd5,32'd8}; record_words[6] = {32'd2,32'd3}; record_words[7] = 32'h00050004;
    record_words[8] = {32'd0,32'h0000ffff}; record_words[9]=0; record_words[10]=0; record_words[11]=64'h123456789abcdef0;
    repeat (4) @(posedge clk); reset <= 0;
    wait (attached && !control_fault);
    wait (input_valid && pcm_valid && command_valid);
    ps2_key <= {1'b1,1'b1,1'b0,8'h1c};
    frame_state[0] <= DIABLO_FRAME_READY; frame_generation[0] <= EPOCH; frame_id[0] <= 64'h101;
    repeat (6) begin pulse_vblank(); repeat (50) @(posedge clk); end
    repeat (4000) @(posedge clk);
    // Stop at a responder boundary: clients may issue another request on the
    // next clock, but no accepted read may be left without its own response.
    while (pending) @(posedge clk);
    #1;
    if (frame_state[0] != DIABLO_FRAME_FPGA_DISPLAYING || input_producer == 0 || input_writes == 0 || pcm_writes == 0 || commands_executed < 3 || command_pixel_writes == 0 || observed_fence != 64'h9abcdef012345678)
      $fatal(1,"FAIL integrated service frame=%b blank=%b states=%h/%h/%h vblankwrites=%0d input=%0d pcmwrites=%0d command=%0d pixelwrites=%0d fence=%h",framebuffer_valid,framebuffer_blank,frame_state[0],frame_state[1],frame_state[2],vblank_writes,input_producer,pcm_writes,commands_executed,command_pixel_writes,observed_fence);
    if (reads != responses || vblank_writes < 1 || command_fault || ddram_fault)
      $fatal(1,"FAIL integrated ownership reads=%0d responses=%0d vblankwrites=%0d command_fault=%b ddram_fault=%b",reads,responses,vblank_writes,command_fault,ddram_fault);
    $display("integrated transport DDR checks passed reads=%0d writes=%0d pcm_depth=%0d underruns=%0d",reads,writes,pcm_depth,underruns);
    $finish;
  end
  initial begin
    repeat (20000) @(posedge clk);
    $fatal(1, "FAIL integrated timeout attached=%b control_fault=%b input=%b pcm=%b command=%b reads=%0d responses=%0d", attached, control_fault, input_valid, pcm_valid, command_valid, reads, responses);
  end
endmodule
