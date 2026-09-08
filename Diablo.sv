//============================================================================
//
//  This program is free software; you can redistribute it and/or modify it
//  under the terms of the GNU General Public License as published by the Free
//  Software Foundation; either version 2 of the License, or (at your option)
//  any later version.
//
//  This program is distributed in the hope that it will be useful, but WITHOUT
//  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
//  FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
//  more details.
//
//  You should have received a copy of the GNU General Public License along
//  with this program; if not, write to the Free Software Foundation, Inc.,
//  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
//
//============================================================================

module emu
(
	`include "sys/emu_ports.vh"
);

///////// Default values for ports not used in this core /////////

assign ADC_BUS  = 'Z;
assign USER_OUT = '1;
assign {UART_RTS, UART_TXD, UART_DTR} = 0;
assign {SD_SCK, SD_MOSI, SD_CS} = 'Z;
assign {SDRAM_DQ, SDRAM_A, SDRAM_BA, SDRAM_CLK, SDRAM_CKE, SDRAM_DQML, SDRAM_DQMH, SDRAM_nWE, SDRAM_nCAS, SDRAM_nRAS, SDRAM_nCS} = 'Z;
assign DDRAM_CLK = clk_sys;

assign VGA_SL = 0;
assign VGA_F1 = 0;
// A valid indexed gameplay frame is consumed through the framework
// framebuffer/scaler path.  Force that path for analog/direct output as well;
// otherwise the core's direct RGB bus would expose the diagnostic generator.
// The diagnostic OSD option deliberately leaves the native pattern selected.
wire diagnostic_video = status[6];
wire gameplay_video_valid;
wire video_startup_error;
wire video_direct_diagnostic;
diablo_video_source_policy video_source_policy (
    .transport_session_valid(transport_session_valid),
    .framebuffer_valid(framebuffer_valid),
    .diagnostic_video(diagnostic_video),
    .gameplay_video_valid(gameplay_video_valid),
    .startup_error(video_startup_error),
    .vga_scaler_enable(VGA_SCALER),
    .framebuffer_enable(FB_EN),
    .direct_diagnostic_enable(video_direct_diagnostic)
);
assign VGA_DISABLE = 0;
assign HDMI_FREEZE = 0;
assign HDMI_BLACKOUT = 0;
assign HDMI_BOB_DEINT = 0;

assign FB_FORMAT = 5'b00011; // indexed 8bpp, palette supplied by the core
assign FB_WIDTH = 12'd640;
assign FB_HEIGHT = 12'd480;
assign FB_STRIDE = 14'd640;
assign FB_FORCE_BLANK = framebuffer_blank;
// Palette writes are synchronous to the core clock. The platform scaler takes
// this core-provided clock as the palette RAM write clock.
assign FB_PAL_CLK = clk_sys;

assign LED_DISK = 0;
assign LED_POWER = 0;
assign BUTTONS = 0;

//////////////////////////////////////////////////////////////////

wire [1:0] ar = status[122:121];

assign VIDEO_ARX = (!ar) ? 12'd4 : (ar - 1'd1);
assign VIDEO_ARY = (!ar) ? 12'd3 : 12'd0;

`include "build_id.v" 
localparam CONF_STR = {
    "Diablo;;",
    "O[122:121],Aspect ratio,Original,Full Screen,[ARC1],[ARC2];",
    "O[6],Video source,Gameplay,Diagnostics;",
    "O[4:3],Test pattern,Color Bars,Pixels,Ramps;",
    "P1,Show controls;",
    "P1-,A: Attack / talk / lift-place / confirm;",
    "P1-,X: Cast / quick equip-belt / hold drop;",
    "P1-,Y: Interact / loot / use-equip-stash;",
    "P1-,B: Speedbook / panel back / safe stow;",
    "P1-,LB/RB: Healing / mana potion;",
    "P1-,LT: Stand ground;",
    "P1-,RT: Modifier only (no action alone);",
    "P1-,RT+X/Y/A/B: Quick spells 1/2/3/4;",
    "P1-,Left stick: Move / Right stick: Cursor;",
    "P1-,L3: Labels / R3: Left click / RT+R3: Right click;",
    "P1-,D-pad up: Spellbook / right: Inventory;",
    "P1-,D-pad down: Quests / left: Character;",
    "P1-,RT+D-pad: Pan automap;",
    "P1-,View: Automap / Menu: Game menu / Guide: OSD;",
    "T[0],Reset;",
    "R[0],Reset and close OSD;",
    "v,1;",
    "V,v",`BUILD_DATE
};

wire forced_scandoubler;
wire   [1:0] buttons;
wire [127:0] status;
wire  [10:0] ps2_key;
wire  [31:0] joystick_0;
wire  [15:0] joystick_l_analog_0;
wire  [15:0] joystick_r_analog_0;
wire  [24:0] ps2_mouse;
wire  [15:0] ps2_mouse_ext;

hps_io #(.CONF_STR(CONF_STR)) hps_io
(
	.clk_sys(clk_sys),
	.HPS_BUS(HPS_BUS),
	.EXT_BUS(),
	.gamma_bus(),

	.forced_scandoubler(forced_scandoubler),

	.buttons(buttons),
	.status(status),
	.status_menumask(16'd0),
	
	.ps2_key(ps2_key),
	.joystick_0(joystick_0),
	.joystick_l_analog_0(joystick_l_analog_0),
	.joystick_r_analog_0(joystick_r_analog_0),
	.ps2_mouse(ps2_mouse),
	.ps2_mouse_ext(ps2_mouse_ext)
);

///////////////////////   CLOCKS   ///////////////////////////////

wire clk_sys;
wire pll_locked;
pll pll (.refclk(CLK_50M), .rst(1'b0), .outclk_0(clk_sys), .locked(pll_locked));

// Assert immediately on loss of lock, release in the core clock domain.
reg [1:0] ready_sync = 0;
always @(posedge clk_sys or negedge pll_locked) begin
    if (!pll_locked) ready_sync <= 0;
    else ready_sync <= {ready_sync[0], 1'b1};
end
reg [1:0] reset_sync = 2'b11;
always @(posedge clk_sys) reset_sync <= {reset_sync[0], RESET};
wire reset = reset_sync[1] | status[0] | buttons[1];

wire transport_attached;
wire transport_fault;
wire transport_ddram_fault;
// A latched shared-DDR fault is a transport-wide stop condition.  Clients are
// quiesced instead of retrying against an arbiter that is deliberately holding
// a timed-out read owner for a possible late response.
wire transport_session_valid = transport_attached && !transport_ddram_fault;
wire [31:0] transport_epoch;
wire [7:0] control_ddram_burstcnt;
wire [28:0] control_ddram_addr;
wire control_ddram_rd;
wire [63:0] control_ddram_din;
wire [7:0] control_ddram_be;
wire control_ddram_we;
diablo_transport_control_reader transport_control (
    .clk(clk_sys), .reset(reset),
    .ddram_busy(control_ddram_busy), .ddram_dout(control_ddram_dout), .ddram_dout_ready(control_ddram_dout_ready),
    .ddram_burstcnt(control_ddram_burstcnt), .ddram_addr(control_ddram_addr), .ddram_rd(control_ddram_rd),
    .ddram_din(control_ddram_din), .ddram_be(control_ddram_be), .ddram_we(control_ddram_we),
    .attached(transport_attached), .fault(transport_fault), .attached_epoch(transport_epoch)
);
wire control_ddram_busy;
wire [63:0] control_ddram_dout;
wire control_ddram_dout_ready;

wire [7:0] frame_ddram_burstcnt;
wire [28:0] frame_ddram_addr;
wire frame_ddram_rd;
wire [63:0] frame_ddram_din;
wire [7:0] frame_ddram_be;
wire frame_ddram_we;
wire framebuffer_valid;
wire [31:0] framebuffer_base;
wire framebuffer_blank;
diablo_framebuffer_scanout frame_scanout (
    .clk(clk_sys), .reset(reset), .session_valid(transport_session_valid), .session_epoch(transport_epoch), .vblank(FB_VBL),
    .ddram_busy(frame_ddram_busy), .ddram_dout(frame_ddram_dout), .ddram_dout_ready(frame_ddram_dout_ready),
    .ddram_burstcnt(frame_ddram_burstcnt), .ddram_addr(frame_ddram_addr), .ddram_rd(frame_ddram_rd),
    .ddram_din(frame_ddram_din), .ddram_be(frame_ddram_be), .ddram_we(frame_ddram_we),
    .framebuffer_valid(framebuffer_valid), .framebuffer_base(framebuffer_base), .framebuffer_blank(framebuffer_blank),
    .fb_pal_clk(FB_PAL_CLK), .fb_pal_addr(FB_PAL_ADDR), .fb_pal_dout(FB_PAL_DOUT), .fb_pal_wr(FB_PAL_WR)
);
wire frame_ddram_busy;
wire [63:0] frame_ddram_dout;
wire frame_ddram_dout_ready;
// Keep the framework framebuffer disabled while the explicit diagnostic source
// is selected. This prevents stale indexed metadata from being presented as
// gameplay during pattern/startup screens; the framework's cfg[12]/cfg[2]
// routing still requires per-mode qualification in C13.
assign FB_BASE = framebuffer_base;

wire [7:0] audio_ddram_burstcnt;
wire [28:0] audio_ddram_addr;
wire audio_ddram_rd;
wire [63:0] audio_ddram_din;
wire [7:0] audio_ddram_be;
wire audio_ddram_we;
wire audio_ddram_busy;
wire [63:0] audio_ddram_dout;
wire audio_ddram_dout_ready;
wire [15:0] pcm_audio_l;
wire [15:0] pcm_audio_r;
wire [31:0] pcm_underrun_count;
wire [31:0] pcm_resync_count;
wire [14:0] pcm_queue_depth;
wire pcm_ring_valid;
wire [63:0] transport_ddram_diagnostic;
diablo_pcm_player #(
    // Keep several callback intervals resident locally.  The FPGA can then
    // absorb DDR arbitration and ARM callback jitter without presenting a
    // zero-length run to the DAC.
    .PRIME_SAMPLES(8192), .FIFO_SAMPLES(16384)
) pcm_player (
    .clk(clk_sys), .reset(reset), .session_valid(transport_session_valid), .session_epoch(transport_epoch),
    .arbiter_diagnostic(transport_ddram_diagnostic),
    .ddram_busy(audio_ddram_busy), .ddram_dout(audio_ddram_dout), .ddram_dout_ready(audio_ddram_dout_ready),
    .ddram_burstcnt(audio_ddram_burstcnt), .ddram_addr(audio_ddram_addr), .ddram_rd(audio_ddram_rd),
    .ddram_din(audio_ddram_din), .ddram_be(audio_ddram_be), .ddram_we(audio_ddram_we),
    .audio_l(pcm_audio_l), .audio_r(pcm_audio_r), .underrun_count(pcm_underrun_count),
    .resync_count(pcm_resync_count), .queue_depth(pcm_queue_depth), .ring_valid(pcm_ring_valid)
);

wire [7:0] input_ddram_burstcnt;
wire [28:0] input_ddram_addr;
wire input_ddram_rd;
wire [63:0] input_ddram_din;
wire [7:0] input_ddram_be;
wire input_ddram_we;
wire input_ddram_busy;
wire [63:0] input_ddram_dout;
wire input_ddram_dout_ready;
wire input_ring_valid;
wire [31:0] input_overflow_count;
diablo_input_capture input_capture (
    .clk(clk_sys), .reset(reset), .session_valid(transport_session_valid), .session_epoch(transport_epoch),
    .joystick_0(joystick_0), .joystick_l_analog_0(joystick_l_analog_0),
    .joystick_r_analog_0(joystick_r_analog_0), .ps2_key(ps2_key),
    .ps2_mouse(ps2_mouse), .ps2_mouse_ext(ps2_mouse_ext), .buttons(buttons),
    .osd_status(OSD_STATUS),
    .ddram_busy(input_ddram_busy), .ddram_dout(input_ddram_dout),
    .ddram_dout_ready(input_ddram_dout_ready), .ddram_burstcnt(input_ddram_burstcnt),
    .ddram_addr(input_ddram_addr), .ddram_rd(input_ddram_rd), .ddram_din(input_ddram_din),
    .ddram_be(input_ddram_be), .ddram_we(input_ddram_we), .ring_valid(input_ring_valid),
    .overflow_count(input_overflow_count)
);

wire [7:0] command_ddram_burstcnt;
wire [28:0] command_ddram_addr;
wire command_ddram_rd;
wire [63:0] command_ddram_din;
wire [7:0] command_ddram_be;
wire command_ddram_we;
wire command_ddram_busy;
wire [63:0] command_ddram_dout;
wire command_ddram_dout_ready;
wire command_ring_valid;
wire command_fault;
wire [31:0] command_count;
wire [31:0] command_rejected;
wire [63:0] command_last_fence;
// The scene publisher acquires a free framebuffer slot. The consumer uses
// the explicit target slot carried by each command record.
diablo_command_consumer command_consumer (
    .clk(clk_sys), .reset(reset), .session_valid(transport_session_valid),
    .session_epoch(transport_epoch), .target_pixel_base(32'h3fe01000),
    .ddram_busy(command_ddram_busy), .ddram_dout(command_ddram_dout),
    .ddram_dout_ready(command_ddram_dout_ready), .ddram_burstcnt(command_ddram_burstcnt),
    .ddram_addr(command_ddram_addr), .ddram_rd(command_ddram_rd),
    .ddram_din(command_ddram_din), .ddram_be(command_ddram_be),
    .ddram_we(command_ddram_we), .ring_valid(command_ring_valid),
    .fault(command_fault), .commands_executed(command_count),
    .commands_rejected(command_rejected), .last_fence(command_last_fence)
);

diablo_transport_ddram_arbiter transport_ddram_arbiter (
    .clk(clk_sys), .reset(reset), .session_valid(transport_session_valid),
    .control_burstcnt(control_ddram_burstcnt), .control_addr(control_ddram_addr), .control_rd(control_ddram_rd),
    .control_din(control_ddram_din), .control_be(control_ddram_be), .control_we(control_ddram_we),
    .control_busy(control_ddram_busy), .control_dout(control_ddram_dout), .control_dout_ready(control_ddram_dout_ready),
    .frame_burstcnt(frame_ddram_burstcnt), .frame_addr(frame_ddram_addr), .frame_rd(frame_ddram_rd),
    .frame_din(frame_ddram_din), .frame_be(frame_ddram_be), .frame_we(frame_ddram_we),
    .frame_busy(frame_ddram_busy), .frame_dout(frame_ddram_dout), .frame_dout_ready(frame_ddram_dout_ready),
    .audio_burstcnt(audio_ddram_burstcnt), .audio_addr(audio_ddram_addr), .audio_rd(audio_ddram_rd),
    .audio_din(audio_ddram_din), .audio_be(audio_ddram_be), .audio_we(audio_ddram_we),
    .audio_busy(audio_ddram_busy), .audio_dout(audio_ddram_dout), .audio_dout_ready(audio_ddram_dout_ready),
    .input_burstcnt(input_ddram_burstcnt), .input_addr(input_ddram_addr), .input_rd(input_ddram_rd),
    .input_din(input_ddram_din), .input_be(input_ddram_be), .input_we(input_ddram_we),
    .input_busy(input_ddram_busy), .input_dout(input_ddram_dout), .input_dout_ready(input_ddram_dout_ready),
    .command_burstcnt(command_ddram_burstcnt), .command_addr(command_ddram_addr), .command_rd(command_ddram_rd),
    .command_din(command_ddram_din), .command_be(command_ddram_be), .command_we(command_ddram_we),
    .command_busy(command_ddram_busy), .command_dout(command_ddram_dout), .command_dout_ready(command_ddram_dout_ready),
    .ddram_busy(DDRAM_BUSY), .ddram_dout(DDRAM_DOUT), .ddram_dout_ready(DDRAM_DOUT_READY),
    .ddram_burstcnt(DDRAM_BURSTCNT), .ddram_addr(DDRAM_ADDR), .ddram_rd(DDRAM_RD),
    .ddram_din(DDRAM_DIN), .ddram_be(DDRAM_BE), .ddram_we(DDRAM_WE),
    .fault(transport_ddram_fault), .diagnostic(transport_ddram_diagnostic)
);

assign AUDIO_S = 1'b1;
assign AUDIO_L = pcm_audio_l;
assign AUDIO_R = pcm_audio_r;
assign AUDIO_MIX = 0;

native_test_pattern pattern (
    .clk(clk_sys), .ready(ready_sync[1]), .reset(reset), .mode(status[4:3]),
    .diagnostic_enable(video_direct_diagnostic), .startup_error(video_startup_error),
    .ddr_probe_pass(transport_session_valid), .ddr_probe_fault(transport_fault || transport_ddram_fault),
    .ce_pixel(CE_PIXEL), .hs(VGA_HS), .vs(VGA_VS), .de(VGA_DE),
    .red(VGA_R), .green(VGA_G), .blue(VGA_B)
);
assign CLK_VIDEO = clk_sys;
assign LED_USER = transport_session_valid;
endmodule
