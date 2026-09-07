`timescale 1ns/1ps
module transport_abi_tb;
    `include "diablo_transport_abi.svh"

    reg [7:0] control [0:DIABLO_TRANSPORT_CONTROL_BYTES - 1];

    function automatic [31:0] le32(input integer offset);
        le32 = { control[offset + 3], control[offset + 2], control[offset + 1], control[offset] };
    endfunction

    function automatic [63:0] le64(input integer offset);
        le64 = { control[offset + 7], control[offset + 6], control[offset + 5], control[offset + 4],
                 control[offset + 3], control[offset + 2], control[offset + 1], control[offset] };
    endfunction

    task automatic expect32(input [31:0] actual, input [31:0] expected, input [8*48-1:0] description);
        begin
            if (actual !== expected) begin
                $display("FAIL %0s: got %08x expected %08x", description, actual, expected);
                $fatal(1);
            end
        end
    endtask

    initial begin
        $readmemh(".work/build/transport-abi/header.hex", control);
        if ({ control[0], control[1], control[2], control[3], control[4], control[5], control[6], control[7] } !== DIABLO_TRANSPORT_MAGIC) begin
            $display("FAIL transport magic");
            $fatal(1);
        end
        expect32(le32(12), DIABLO_TRANSPORT_CONTROL_BYTES, "control bytes");
        expect32(le32(16), DIABLO_TRANSPORT_SHARED_BYTES, "shared bytes");
        expect32(le32(20), DIABLO_TRANSPORT_LITTLE_ENDIAN_TAG, "endian tag");
        expect32(le32(DIABLO_TRANSPORT_HEADER_INPUT_OFFSET), 32'h01020408, "input producer walking bits");
        expect32(le32(DIABLO_TRANSPORT_HEADER_INPUT_OFFSET + 4), 32'h10204080, "input consumer walking bits");
        expect32(le32(DIABLO_TRANSPORT_HEADER_INPUT_OFFSET + 8), DIABLO_TRANSPORT_INPUT_CAPACITY, "input capacity");
        expect32(le32(DIABLO_TRANSPORT_HEADER_INPUT_OFFSET + 12), DIABLO_TRANSPORT_INPUT_RECORD_BYTES, "input record bytes");
        expect32(le32(DIABLO_TRANSPORT_HEADER_FRAMES_OFFSET + 2 * DIABLO_TRANSPORT_FRAME_RECORD_BYTES), DIABLO_FRAME_FAULT, "frame state");
        if (le64(DIABLO_TRANSPORT_HEADER_FRAMES_OFFSET + 2 * DIABLO_TRANSPORT_FRAME_RECORD_BYTES + DIABLO_TRANSPORT_FRAME_ID_OFFSET) !== 64'h0102030405060708) begin
            $display("FAIL frame ID packing");
            $fatal(1);
        end
        expect32(le32(DIABLO_TRANSPORT_HEADER_FRAMES_OFFSET + 2 * DIABLO_TRANSPORT_FRAME_RECORD_BYTES + DIABLO_TRANSPORT_FRAME_PIXEL_OFFSET_OFFSET), diablo_transport_frame_offset(2), "frame pixel offset");
        expect32(le32(DIABLO_TRANSPORT_HEADER_FRAMES_OFFSET + 2 * DIABLO_TRANSPORT_FRAME_RECORD_BYTES + DIABLO_TRANSPORT_FRAME_PALETTE_OFFSET_OFFSET), diablo_transport_palette_offset(2), "frame palette offset");
        if (le64(DIABLO_TRANSPORT_HEADER_FRAMES_OFFSET + 2 * DIABLO_TRANSPORT_FRAME_RECORD_BYTES + DIABLO_TRANSPORT_FRAME_FENCE_OFFSET) !== 64'h1020304050607080) begin
            $display("FAIL frame fence packing");
            $fatal(1);
        end
        expect32(le32(392 + 8), 32'hFFFFCFC7, "negative mouse X packing");
        expect32(le32(392 + 12), 32'd23456, "mouse Y packing");
        expect32(le32(392 + 24), 32'h0F0E0D0C, "input modifiers");
        $display("transport ABI C++/RTL layout checks passed");
        $finish;
    end
endmodule
