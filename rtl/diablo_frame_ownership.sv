// Frame ownership policy for the shared ARM/FPGA transport ABI.
// A future f2h-DDR control-page reader supplies these metadata snapshots and
// performs the emitted claim/retire writes. This module never assumes an
// absolute DDR address and cannot expose a displayed slot to the ARM writer.
module diablo_frame_ownership (
    input  wire         clk,
    input  wire         reset,
    input  wire         session_valid,
    input  wire [31:0]  session_epoch,
    input  wire         vblank,

    input  wire [95:0]  slot_state,
    input  wire [95:0]  slot_generation,
    input  wire [191:0] slot_frame_id,
    input  wire [95:0]  slot_pixel_offset,
    input  wire [95:0]  slot_pixel_bytes,
    input  wire [95:0]  slot_palette_offset,
    input  wire [95:0]  slot_palette_bytes,

    output reg          claim_valid,
    output reg  [1:0]   claim_slot,
    output reg  [63:0]  claim_frame_id,
    input  wire         claim_result_valid,
    input  wire         claim_granted,

    output reg          display_valid,
    output reg  [1:0]   display_slot,
    output reg  [63:0]  display_frame_id,
    output reg          display_switch,
    output reg          retire_valid,
    output reg  [1:0]   retire_slot,
    output reg          fault_valid,
    output reg  [1:0]   fault_slot,
    output reg  [31:0]  fault_code
);

`include "diablo_transport_abi.svh"

localparam [31:0] FAULT_STALE_EPOCH  = 32'd1;
localparam [31:0] FAULT_BAD_LAYOUT   = 32'd2;

reg         pending_valid;
reg  [1:0]  pending_slot;
reg  [63:0] pending_frame_id;
reg         candidate_valid;
reg  [1:0]  candidate_slot;
reg  [63:0] candidate_frame_id;
reg         bad_descriptor;
reg  [1:0]  bad_descriptor_slot;
reg  [31:0] bad_descriptor_code;

function automatic [31:0] slot32(input [95:0] values, input integer slot);
    slot32 = values[slot * 32 +: 32];
endfunction

function automatic [63:0] slot64(input [191:0] values, input integer slot);
    slot64 = values[slot * 64 +: 64];
endfunction

integer i;
always @* begin
    candidate_valid = 1'b0;
    candidate_slot = 0;
    candidate_frame_id = 0;
    bad_descriptor = 1'b0;
    bad_descriptor_slot = 0;
    bad_descriptor_code = 0;
    for (i = 0; i < DIABLO_TRANSPORT_FRAME_SLOTS; i = i + 1) begin
        if (slot32(slot_state, i) == DIABLO_FRAME_READY) begin
            if (slot32(slot_generation, i) != session_epoch) begin
                bad_descriptor = 1'b1;
                bad_descriptor_slot = i[1:0];
                bad_descriptor_code = FAULT_STALE_EPOCH;
            end else if (slot32(slot_pixel_offset, i) != diablo_transport_frame_offset(i)
                     || slot32(slot_pixel_bytes, i) != DIABLO_TRANSPORT_FRAME_PIXEL_BYTES
                     || slot32(slot_palette_offset, i) != diablo_transport_palette_offset(i)
                     || slot32(slot_palette_bytes, i) != DIABLO_TRANSPORT_PALETTE_BYTES) begin
                bad_descriptor = 1'b1;
                bad_descriptor_slot = i[1:0];
                bad_descriptor_code = FAULT_BAD_LAYOUT;
            end else if ((!display_valid || slot64(slot_frame_id, i) > display_frame_id)
                     && (!candidate_valid || slot64(slot_frame_id, i) > candidate_frame_id)) begin
                candidate_valid = 1'b1;
                candidate_slot = i[1:0];
                candidate_frame_id = slot64(slot_frame_id, i);
            end
        end
    end
end

always @(posedge clk) begin
    claim_valid <= 1'b0;
    display_switch <= 1'b0;
    retire_valid <= 1'b0;
    fault_valid <= 1'b0;
    if (reset || !session_valid) begin
        display_valid <= 1'b0;
        display_slot <= 0;
        display_frame_id <= 0;
        pending_valid <= 1'b0;
        pending_slot <= 0;
        pending_frame_id <= 0;
    end else begin
        if (bad_descriptor) begin
            fault_valid <= 1'b1;
            fault_slot <= bad_descriptor_slot;
            fault_code <= bad_descriptor_code;
        end
        if (pending_valid && claim_result_valid) begin
            if (claim_granted) begin
                if (display_valid) begin
                    retire_valid <= 1'b1;
                    retire_slot <= display_slot;
                end
                display_valid <= 1'b1;
                display_slot <= pending_slot;
                display_frame_id <= pending_frame_id;
                display_switch <= 1'b1;
            end
            pending_valid <= 1'b0;
        end
        if (vblank && !pending_valid && candidate_valid && !bad_descriptor) begin
            claim_valid <= 1'b1;
            claim_slot <= candidate_slot;
            claim_frame_id <= candidate_frame_id;
            pending_valid <= 1'b1;
            pending_slot <= candidate_slot;
            pending_frame_id <= candidate_frame_id;
        end
    end
end

endmodule
