// Indexed ARM-frame scanout for the validated MiSTer shared-DDR reservation.
// Pixels stay in DDR and use the platform's 128-bit framebuffer port. This
// module uses the ordinary core DDR port only for six descriptor words and the
// 768-byte RGB palette when it claims a new slot.
module diablo_framebuffer_scanout (
    input wire clk,
    input wire reset,
    input wire session_valid,
    input wire [31:0] session_epoch,
    input wire vblank,

    input wire ddram_busy,
    input wire [63:0] ddram_dout,
    input wire ddram_dout_ready,
    output wire [7:0] ddram_burstcnt,
    output wire [28:0] ddram_addr,
    output wire ddram_rd,
    output wire [63:0] ddram_din,
    output wire [7:0] ddram_be,
    output wire ddram_we,

    output reg framebuffer_valid = 1'b0,
    output reg [31:0] framebuffer_base = 32'h3fe01000,
    output reg framebuffer_blank = 1'b0,
    input wire fb_pal_clk,
    output wire [7:0] fb_pal_addr,
    output wire [23:0] fb_pal_dout,
    output wire fb_pal_wr
);
    `include "diablo_transport_abi.svh"

    localparam [28:0] SHARED_BASE_WORD = 29'h07fc0000;
    localparam [31:0] SHARED_BASE_BYTE = 32'h3fe00000;
    localparam [3:0] IDLE = 4'd0;
    localparam [3:0] METADATA_REQUEST = 4'd1;
    localparam [3:0] METADATA_WAIT = 4'd2;
    localparam [3:0] EVALUATE = 4'd3;
    localparam [3:0] CLAIM_REQUEST = 4'd4;
    localparam [3:0] CLAIM_COMPLETE = 4'd5;
    localparam [3:0] PALETTE_REQUEST = 4'd6;
    localparam [3:0] PALETTE_WAIT = 4'd7;
    localparam [3:0] PALETTE_CONSUME = 4'd8;
    localparam [3:0] PALETTE_COMMIT = 4'd9;
    localparam [3:0] PALETTE_ACK_WAIT = 4'd10;
    localparam [3:0] RETIRE_REQUEST = 4'd11;
    localparam [3:0] RETIRE_FRAME_EPOCH = 4'd12;
    localparam [3:0] RETIRE_LAST_FRAME_ID = 4'd13;
    localparam [3:0] RETIRE_DISPLAY_EPOCH = 4'd14;
    // A ready frame older than the active frame was superseded before it could
    // be displayed. Release only its FPGA-owned state half; it must not affect
    // presentation counters or claim that it reached scanout.
    localparam [3:0] DISCARD_REQUEST = 4'd15;

    reg [3:0] state = IDLE;
    reg vblank_d = 1'b0;
    wire vblank_rise = vblank & ~vblank_d;
    reg [2:0] metadata_index = 0;
    reg [31:0] slot_state [0:2];
    reg [31:0] slot_generation [0:2];
    reg [63:0] slot_frame_id [0:2];
    reg [1:0] claim_slot = 0;
    reg [63:0] claim_frame_id = 0;
    reg [1:0] pending_slot = 0;
    reg [63:0] pending_frame_id = 0;
    reg pending_valid = 1'b0;
    reg [1:0] active_slot = 0;
    reg [63:0] active_frame_id = 0;
    reg [1:0] retire_slot = 0;
    reg [63:0] retire_frame_id = 0;
    reg [31:0] display_epoch_counter = 0;

    (* ramstyle = "M10K, no_rw_check" *) reg [23:0] palette [0:255];
    reg [6:0] palette_word_index = 0;
    reg [2:0] palette_byte_lane = 0;
    reg [1:0] palette_component = 0;
    reg [7:0] palette_entry = 0;
    reg [7:0] palette_red = 0;
    reg [7:0] palette_green = 0;
    reg [63:0] palette_word = 0;
    reg palette_commit_toggle = 1'b0;
    reg palette_ack_sync_1 = 1'b0;
    reg palette_ack_sync_2 = 1'b0;

    reg [1:0] candidate_slot;
    reg [63:0] candidate_frame_id;
    reg candidate_valid;
    reg [1:0] stale_slot;
    reg stale_valid;
    integer i;
    always @* begin
        candidate_slot = 0;
        candidate_frame_id = 0;
        candidate_valid = 1'b0;
		stale_slot = 0;
		stale_valid = 1'b0;
        for (i = 0; i < 3; i = i + 1) begin
            if (slot_state[i] == DIABLO_FRAME_READY
             && slot_generation[i] == session_epoch
             && (!framebuffer_valid || slot_frame_id[i] > active_frame_id)
             && (!pending_valid || slot_frame_id[i] > pending_frame_id)
             // Present the oldest eligible frame. With a three-slot pipeline
             // this gives every submitted frame a terminal ownership outcome
             // instead of permanently stranding a skipped newer-selection
             // candidate in READY.
             && (!candidate_valid || slot_frame_id[i] < candidate_frame_id)) begin
                candidate_slot = i[1:0];
                candidate_frame_id = slot_frame_id[i];
                candidate_valid = 1'b1;
            end
			if (framebuffer_valid
			 && slot_state[i] == DIABLO_FRAME_READY
			 && slot_generation[i] == session_epoch
			 && slot_frame_id[i] <= active_frame_id) begin
				stale_slot = i[1:0];
				stale_valid = 1'b1;
			end
        end
    end

    function automatic [28:0] metadata_address(input [2:0] index);
        begin
            case (index)
                3'd0: metadata_address = SHARED_BASE_WORD + 29'd22;
                3'd1: metadata_address = SHARED_BASE_WORD + 29'd23;
                3'd2: metadata_address = SHARED_BASE_WORD + 29'd30;
                3'd3: metadata_address = SHARED_BASE_WORD + 29'd31;
                3'd4: metadata_address = SHARED_BASE_WORD + 29'd38;
                default: metadata_address = SHARED_BASE_WORD + 29'd39;
            endcase
        end
    endfunction

    function automatic [28:0] slot_state_address(input [1:0] slot);
        begin
            slot_state_address = SHARED_BASE_WORD + 29'd22 + {slot, 3'd0};
        end
    endfunction

    function automatic [28:0] slot_palette_address(input [1:0] slot, input [6:0] word_index);
        begin
            slot_palette_address = SHARED_BASE_WORD
                + (diablo_transport_palette_offset(slot) >> 3) + word_index;
        end
    endfunction

    function automatic [31:0] slot_pixel_base(input [1:0] slot);
        begin
            slot_pixel_base = SHARED_BASE_BYTE + diablo_transport_frame_offset(slot);
        end
    endfunction

    assign ddram_burstcnt = 8'd1;
    assign ddram_rd = (state == METADATA_REQUEST) || (state == PALETTE_REQUEST);
    assign ddram_we = (state == CLAIM_REQUEST) || (state == RETIRE_REQUEST)
                    || (state == RETIRE_FRAME_EPOCH) || (state == RETIRE_LAST_FRAME_ID)
                    || (state == RETIRE_DISPLAY_EPOCH) || (state == DISCARD_REQUEST);
    assign ddram_addr = (state == METADATA_REQUEST) ? metadata_address(metadata_index) :
                        (state == PALETTE_REQUEST) ? slot_palette_address(claim_slot, palette_word_index) :
                        (state == CLAIM_REQUEST) ? slot_state_address(claim_slot) :
                        (state == RETIRE_REQUEST) ? slot_state_address(retire_slot) :
						(state == DISCARD_REQUEST) ? slot_state_address(stale_slot) :
                        (state == RETIRE_FRAME_EPOCH) ? (SHARED_BASE_WORD + 29'd27 + {retire_slot, 3'd0}) :
                        (state == RETIRE_LAST_FRAME_ID) ? (SHARED_BASE_WORD + 29'd46) :
                        (SHARED_BASE_WORD + 29'd48);
    assign ddram_din = (state == CLAIM_REQUEST)
                     ? {32'd0, DIABLO_FRAME_FPGA_DISPLAYING}
                     : (state == RETIRE_FRAME_EPOCH)
                     ? {display_epoch_counter, session_epoch}
                     : (state == RETIRE_LAST_FRAME_ID)
                     ? retire_frame_id
                     : (state == RETIRE_DISPLAY_EPOCH)
                     ? {32'd0, display_epoch_counter}
                     : {32'd0, DIABLO_FRAME_FREE};
    // ARM owns the generation half of a frame state word. Both FPGA state
    // changes update the state half only, so an ARM reset cannot be clobbered.
    assign ddram_be = (state == RETIRE_FRAME_EPOCH) ? 8'hf0
                    : (state == RETIRE_LAST_FRAME_ID) ? 8'hff
                    : 8'h0f;

    reg palette_commit_sync_1 = 1'b0;
    reg palette_commit_sync_2 = 1'b0;
    reg palette_commit_seen = 1'b0;
    reg palette_uploading = 1'b0;
    reg [7:0] palette_upload_address = 0;
    reg palette_ack_toggle = 1'b0;
    always @(posedge fb_pal_clk) begin
        if (reset) begin
            palette_commit_sync_1 <= 1'b0;
            palette_commit_sync_2 <= 1'b0;
            palette_commit_seen <= 1'b0;
            palette_uploading <= 1'b0;
            palette_upload_address <= 0;
            palette_ack_toggle <= 1'b0;
        end else begin
            palette_commit_sync_1 <= palette_commit_toggle;
            palette_commit_sync_2 <= palette_commit_sync_1;
            if (!palette_uploading && palette_commit_sync_2 != palette_commit_seen) begin
                palette_uploading <= 1'b1;
                palette_upload_address <= 0;
            end else if (palette_uploading) begin
                if (palette_upload_address == 8'hff) begin
                    palette_uploading <= 1'b0;
                    palette_commit_seen <= palette_commit_sync_2;
                    palette_ack_toggle <= ~palette_ack_toggle;
                end else begin
                    palette_upload_address <= palette_upload_address + 1'b1;
                end
            end
        end
    end
    assign fb_pal_addr = palette_upload_address;
    assign fb_pal_dout = palette[palette_upload_address];
    assign fb_pal_wr = palette_uploading;

    always @(posedge clk) begin
        vblank_d <= vblank;
        palette_ack_sync_1 <= palette_ack_toggle;
        palette_ack_sync_2 <= palette_ack_sync_1;
        if (reset || !session_valid) begin
            state <= IDLE;
            metadata_index <= 0;
            claim_slot <= 0;
            claim_frame_id <= 0;
            pending_slot <= 0;
            pending_frame_id <= 0;
            pending_valid <= 1'b0;
            active_slot <= 0;
            active_frame_id <= 0;
            retire_slot <= 0;
            retire_frame_id <= 0;
            display_epoch_counter <= 0;
            framebuffer_valid <= 1'b0;
            framebuffer_base <= slot_pixel_base(0);
            framebuffer_blank <= 1'b0;
            palette_word_index <= 0;
            palette_byte_lane <= 0;
            palette_component <= 0;
            palette_entry <= 0;
            palette_red <= 0;
            palette_green <= 0;
            palette_word <= 0;
            palette_commit_toggle <= 1'b0;
        end else begin
            case (state)
                IDLE: begin
                    if (vblank_rise && pending_valid) begin
                        if (framebuffer_valid) begin
                            retire_slot <= active_slot;
                            retire_frame_id <= active_frame_id;
                            display_epoch_counter <= display_epoch_counter + 1'b1;
                            // The old slot is no longer selected after this
                            // vblank. Schedule its ownership writes
                            // immediately so the three-slot pipeline does not
                            // add another frame of backpressure.
                            state <= RETIRE_REQUEST;
						end else begin
							// First activation has no displayed slot to retire. Start
							// staging the next descriptor immediately instead of
							// waiting for another refresh boundary.
							metadata_index <= 0;
							state <= METADATA_REQUEST;
                        end
                        active_slot <= pending_slot;
                        active_frame_id <= pending_frame_id;
                        framebuffer_base <= slot_pixel_base(pending_slot);
                        framebuffer_valid <= 1'b1;
                        framebuffer_blank <= 1'b0;
                        pending_valid <= 1'b0;
                    end else if (stale_valid) begin
						// A pre-existing old READY descriptor cannot be presented
						// after active_frame_id. Return it to the ARM without
						// fabricating a display acknowledgement.
						metadata_index <= 0;
						state <= DISCARD_REQUEST;
					end else if (!pending_valid) begin
						// Descriptor and palette staging are independent of vblank.
						// The completed pair waits in pending_valid until the next
						// boundary, allowing a new activation every refresh once
						// the pipeline is warm.
                        metadata_index <= 0;
                        state <= METADATA_REQUEST;
                    end
                end
                METADATA_REQUEST: if (!ddram_busy) state <= METADATA_WAIT;
                METADATA_WAIT: if (ddram_dout_ready) begin
                    case (metadata_index)
                        3'd0: begin slot_state[0] <= ddram_dout[31:0]; slot_generation[0] <= ddram_dout[63:32]; end
                        3'd1: slot_frame_id[0] <= ddram_dout;
                        3'd2: begin slot_state[1] <= ddram_dout[31:0]; slot_generation[1] <= ddram_dout[63:32]; end
                        3'd3: slot_frame_id[1] <= ddram_dout;
                        3'd4: begin slot_state[2] <= ddram_dout[31:0]; slot_generation[2] <= ddram_dout[63:32]; end
                        default: slot_frame_id[2] <= ddram_dout;
                    endcase
                    if (metadata_index == 3'd5) state <= EVALUATE;
                    else begin
                        metadata_index <= metadata_index + 1'b1;
                        state <= METADATA_REQUEST;
                    end
                end
                EVALUATE: begin
                    if (candidate_valid) begin
                        claim_slot <= candidate_slot;
                        claim_frame_id <= candidate_frame_id;
                        state <= CLAIM_REQUEST;
                    end else begin
                        state <= IDLE;
                    end
                end
                CLAIM_REQUEST: if (!ddram_busy) state <= CLAIM_COMPLETE;
                CLAIM_COMPLETE: begin
                    palette_word_index <= 0;
                    palette_byte_lane <= 0;
                    palette_component <= 0;
                    palette_entry <= 0;
                    palette_red <= 0;
                    palette_green <= 0;
                    state <= PALETTE_REQUEST;
                end
                PALETTE_REQUEST: if (!ddram_busy) state <= PALETTE_WAIT;
                PALETTE_WAIT: if (ddram_dout_ready) begin
                    palette_word <= ddram_dout;
                    palette_byte_lane <= 0;
                    state <= PALETTE_CONSUME;
                end
                PALETTE_CONSUME: begin
                    case (palette_component)
                        0: palette_red <= palette_word[palette_byte_lane * 8 +: 8];
                        1: palette_green <= palette_word[palette_byte_lane * 8 +: 8];
                        default: palette[palette_entry] <= {palette_red, palette_green,
                                                            palette_word[palette_byte_lane * 8 +: 8]};
                    endcase
                    palette_component <= (palette_component == 2) ? 0 : palette_component + 1'b1;
                    if (palette_component == 2) palette_entry <= palette_entry + 1'b1;
                    if (palette_byte_lane == 3'd7) begin
                        if (palette_word_index == 7'd95) state <= PALETTE_COMMIT;
                        else begin
                            palette_word_index <= palette_word_index + 1'b1;
                            state <= PALETTE_REQUEST;
                        end
                    end else begin
                        palette_byte_lane <= palette_byte_lane + 1'b1;
                    end
                end
                PALETTE_COMMIT: if (vblank_rise) begin
                    // The scaler palette is live. Start its staged 256-entry
                    // upload only in vertical blank, and retain blanking if an
                    // unexpected delay carries the upload beyond this interval.
                    // The old framebuffer can therefore never be scanned with
                    // the palette belonging to the new one.
                    framebuffer_blank <= 1'b1;
                    palette_commit_toggle <= ~palette_commit_toggle;
                    state <= PALETTE_ACK_WAIT;
                end
                PALETTE_ACK_WAIT: if (palette_ack_sync_2 == palette_commit_toggle) begin
                    if (vblank) begin
                        // The staged palette and frame base now commit during
                        // the same blanking interval. Activate immediately so
                        // a prepared frame does not need another vblank.
                        if (framebuffer_valid) begin
                            retire_slot <= active_slot;
                            retire_frame_id <= active_frame_id;
                            display_epoch_counter <= display_epoch_counter + 1'b1;
                            state <= RETIRE_REQUEST;
                        end else begin
                            metadata_index <= 0;
                            state <= METADATA_REQUEST;
                        end
                        active_slot <= claim_slot;
                        active_frame_id <= claim_frame_id;
                        framebuffer_base <= slot_pixel_base(claim_slot);
                        framebuffer_valid <= 1'b1;
                        framebuffer_blank <= 1'b0;
                        pending_valid <= 1'b0;
                    end else begin
                        // If blanking was unexpectedly too short, keep output
                        // blank and perform the already-paired activation at
                        // the next boundary rather than expose mixed pixels.
                        pending_slot <= claim_slot;
                        pending_frame_id <= claim_frame_id;
                        pending_valid <= 1'b1;
                        state <= IDLE;
                    end
                end
                RETIRE_REQUEST: if (!ddram_busy) state <= RETIRE_FRAME_EPOCH;
                RETIRE_FRAME_EPOCH: begin
                    if (!ddram_busy) begin
                        state <= RETIRE_LAST_FRAME_ID;
                    end
                end
                RETIRE_LAST_FRAME_ID: if (!ddram_busy) state <= RETIRE_DISPLAY_EPOCH;
                RETIRE_DISPLAY_EPOCH: if (!ddram_busy) begin
					metadata_index <= 0;
					state <= METADATA_REQUEST;
				end
				DISCARD_REQUEST: if (!ddram_busy) state <= METADATA_REQUEST;
                default: state <= IDLE;
            endcase
        end
    end
endmodule
