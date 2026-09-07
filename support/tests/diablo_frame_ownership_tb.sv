`timescale 1ns/1ps
module diablo_frame_ownership_tb;
    `include "diablo_transport_abi.svh"

    reg clk = 0;
    always #5 clk = ~clk;
    reg reset = 1;
    reg session_valid = 0;
    reg [31:0] session_epoch = 0;
    reg vblank = 0;
    reg [95:0] slot_state = 0;
    reg [95:0] slot_generation = 0;
    reg [191:0] slot_frame_id = 0;
    reg [95:0] slot_pixel_offset = 0;
    reg [95:0] slot_pixel_bytes = 0;
    reg [95:0] slot_palette_offset = 0;
    reg [95:0] slot_palette_bytes = 0;
    wire claim_valid;
    wire [1:0] claim_slot;
    wire [63:0] claim_frame_id;
    reg claim_result_valid = 0;
    reg claim_granted = 0;
    wire display_valid;
    wire [1:0] display_slot;
    wire [63:0] display_frame_id;
    wire display_switch;
    wire retire_valid;
    wire [1:0] retire_slot;
    wire fault_valid;
    wire [1:0] fault_slot;
    wire [31:0] fault_code;

    diablo_frame_ownership dut (.*);

    task automatic set_valid_slot(input integer slot, input [63:0] frame_id);
        begin
            slot_state[slot * 32 +: 32] = DIABLO_FRAME_READY;
            slot_generation[slot * 32 +: 32] = session_epoch;
            slot_frame_id[slot * 64 +: 64] = frame_id;
            slot_pixel_offset[slot * 32 +: 32] = diablo_transport_frame_offset(slot);
            slot_pixel_bytes[slot * 32 +: 32] = DIABLO_TRANSPORT_FRAME_PIXEL_BYTES;
            slot_palette_offset[slot * 32 +: 32] = diablo_transport_palette_offset(slot);
            slot_palette_bytes[slot * 32 +: 32] = DIABLO_TRANSPORT_PALETTE_BYTES;
        end
    endtask

    task automatic tick;
        begin
            @(negedge clk);
            @(posedge clk);
            #1;
        end
    endtask

    initial begin
        repeat (2) tick;
        reset = 0;
        session_valid = 1;
        session_epoch = 32'hA5010204;
        set_valid_slot(0, 64'd10);
        vblank = 1;
        tick;
        if (!claim_valid || claim_slot != 0 || claim_frame_id != 10) $fatal(1, "did not claim first valid slot at vblank");
        vblank = 0;
        claim_result_valid = 1;
        claim_granted = 1;
        tick;
        if (!display_valid || display_slot != 0 || display_frame_id != 10 || !display_switch || retire_valid) $fatal(1, "first display commit wrong");
        claim_result_valid = 0;

        set_valid_slot(1, 64'd11);
        tick;
        if (claim_valid || display_switch || retire_valid) $fatal(1, "switched outside vblank");
        vblank = 1;
        tick;
        if (!claim_valid || claim_slot != 1) $fatal(1, "did not claim replacement slot");
        vblank = 0;
        claim_result_valid = 1;
        claim_granted = 0;
        tick;
        if (display_slot != 0 || display_switch || retire_valid) $fatal(1, "denied claim disturbed displayed slot");
        claim_result_valid = 0;
        vblank = 1;
        tick;
        if (!claim_valid || claim_slot != 1) $fatal(1, "denied claim was not retried");
        vblank = 0;
        claim_result_valid = 1;
        claim_granted = 1;
        tick;
        if (display_slot != 1 || !display_switch || !retire_valid || retire_slot != 0) $fatal(1, "replacement did not retire old slot atomically");
        claim_result_valid = 0;

        set_valid_slot(2, 64'd12);
        slot_palette_offset[2 * 32 +: 32] = diablo_transport_palette_offset(2) + 4;
        vblank = 1;
        tick;
        if (claim_valid || !fault_valid || fault_slot != 2 || fault_code != 2) $fatal(1, "malformed descriptor was not rejected");
        vblank = 0;
        session_epoch = 32'hA5010205;
        tick;
        if (!fault_valid || fault_code != 1) $fatal(1, "stale epoch was not reported");
        session_valid = 0;
        tick;
        if (display_valid) $fatal(1, "display remained valid across session loss");
        $display("diablo frame ownership RTL checks passed");
        $finish;
    end
endmodule
