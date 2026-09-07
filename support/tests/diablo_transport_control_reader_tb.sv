`timescale 1ns/1ps
module diablo_transport_control_reader_tb;
    `include "diablo_transport_abi.svh"

    localparam [28:0] SHARED_BASE_WORD = 29'h07FC0000;
    reg clk = 0;
    reg reset = 1;
    reg ddram_busy = 0;
    reg [63:0] ddram_dout = 0;
    reg ddram_dout_ready = 0;
    wire [7:0] ddram_burstcnt;
    wire [28:0] ddram_addr;
    wire ddram_rd;
    wire [63:0] ddram_din;
    wire [7:0] ddram_be;
    wire ddram_we;
    wire attached;
    wire fault;
    wire [31:0] attached_epoch;

    reg [63:0] memory [0:63];
    reg read_pending = 0;
    reg write_pending = 0;
    reg [5:0] pending_word = 0;
    integer i;
    integer byte_index;

    diablo_transport_control_reader #(.RETRY_DELAY_CYCLES(4), .RECHECK_DELAY_CYCLES(8)) dut (.*);

    always #5 clk = ~clk;

    function automatic [31:0] frame_offset(input [31:0] slot);
        frame_offset = diablo_transport_frame_offset(slot);
    endfunction

    task automatic write_valid_header;
        input [31:0] epoch;
        integer slot;
        integer base;
        begin
            for (i = 0; i < 64; i = i + 1) memory[i] = 0;
            memory[0] = DIABLO_TRANSPORT_MAGIC_LE64;
            memory[1] = {DIABLO_TRANSPORT_CONTROL_BYTES, DIABLO_TRANSPORT_ABI_MINOR, DIABLO_TRANSPORT_ABI_MAJOR};
            memory[2] = {DIABLO_TRANSPORT_LITTLE_ENDIAN_TAG, DIABLO_TRANSPORT_SHARED_BYTES};
            memory[3] = {epoch, 32'd0};
            memory[4] = {DIABLO_COMPONENT_OFFLINE, DIABLO_COMPONENT_READY};
            for (slot = 0; slot < 3; slot = slot + 1) begin
                base = 22 + slot * 8;
                memory[base] = {epoch, DIABLO_FRAME_FREE};
                memory[base + 3] = {DIABLO_TRANSPORT_FRAME_PIXEL_BYTES, frame_offset(slot)};
                memory[base + 4] = {DIABLO_TRANSPORT_PALETTE_BYTES, diablo_transport_palette_offset(slot)};
                // A live slot may already carry an FPGA-written display
                // epoch; the control reader must preserve and accept it.
                memory[base + 5] = {32'd7, epoch};
            end
        end
    endtask

    always @(posedge clk) begin
        ddram_dout_ready <= 0;
        if (read_pending) begin
            ddram_dout <= memory[pending_word];
            ddram_dout_ready <= 1;
            ddram_busy <= 0;
            read_pending <= 0;
        end else if (write_pending) begin
            ddram_busy <= 0;
            write_pending <= 0;
        end else if (ddram_rd && !ddram_busy) begin
            pending_word <= ddram_addr - SHARED_BASE_WORD;
            ddram_busy <= 1;
            read_pending <= 1;
        end else if (ddram_we && !ddram_busy) begin
            for (byte_index = 0; byte_index < 8; byte_index = byte_index + 1)
                if (ddram_be[byte_index])
                    memory[ddram_addr - SHARED_BASE_WORD][byte_index * 8 +: 8] <= ddram_din[byte_index * 8 +: 8];
            ddram_busy <= 1;
            write_pending <= 1;
        end
    end

    initial begin
        write_valid_header(32'h2a);
        repeat (3) @(posedge clk);
        reset = 0;
        wait (attached === 1'b1);
        if (attached_epoch !== 32'h2a || memory[4] !== {DIABLO_COMPONENT_READY, DIABLO_COMPONENT_READY}
            || memory[5] !== 64'd0) begin
            $display("FAIL ready state write: state=%h fault=%h", memory[4], memory[5]);
            $fatal(1);
        end
        // A new ARM session must be accepted without reloading the RBF. The
        // monitor keeps a healthy attachment live, then detaches and performs
        // the full bounded validation only after the epoch changes, even when
        // the ARM has already published non-free slots.
        memory[22][31:0] = DIABLO_FRAME_READY;
        memory[30][31:0] = DIABLO_FRAME_FPGA_DISPLAYING;
        memory[38][31:0] = DIABLO_FRAME_RETIRED;
        write_valid_header(32'h2b);
        memory[22][31:0] = DIABLO_FRAME_READY;
        memory[30][31:0] = DIABLO_FRAME_FPGA_DISPLAYING;
        memory[38][31:0] = DIABLO_FRAME_RETIRED;
        wait (attached_epoch === 32'h2b);
        if (!attached || memory[4] !== {DIABLO_COMPONENT_READY, DIABLO_COMPONENT_READY}
            || memory[5] !== 64'd0) begin
            $display("FAIL live epoch reattach: epoch=%h state=%h fault=%h", attached_epoch, memory[4], memory[5]);
            $fatal(1);
        end
        // A clean relaunch can publish an all-FREE page before its first
        // frame. That case must reattach just like a page with in-flight
        // descriptors.
        write_valid_header(32'h2e);
        memory[27] = {32'd0, 32'h2e};
        memory[35] = {32'd0, 32'h2e};
        memory[43] = {32'd0, 32'h2e};
        wait (attached_epoch === 32'h2e);
        if (!attached || memory[4] !== {DIABLO_COMPONENT_READY, DIABLO_COMPONENT_READY}
            || memory[5] !== 64'd0) begin
            $display("FAIL all-free epoch reattach: epoch=%h state=%h fault=%h", attached_epoch, memory[4], memory[5]);
            $fatal(1);
        end
        reset = 1;
        repeat (2) @(posedge clk);
        write_valid_header(32'h2c);
        memory[0] = 64'h0;
        reset = 0;
        wait (fault === 1'b1);
        if (memory[4][63:32] !== DIABLO_COMPONENT_FAULT || memory[5][31:0] !== 32'd1) begin
            $display("FAIL fault state write: state=%h code=%h", memory[4], memory[5]);
            $fatal(1);
        end
        memory[0] = DIABLO_TRANSPORT_MAGIC_LE64;
        wait (attached === 1'b1);
        if (attached_epoch !== 32'h2c || memory[4] !== {DIABLO_COMPONENT_READY, DIABLO_COMPONENT_READY}
            || memory[5] !== 64'd0) begin
            $display("FAIL recovery did not preserve ARM state: state=%h fault=%h", memory[4], memory[5]);
            $fatal(1);
        end
        reset = 1;
        repeat (2) @(posedge clk);
        write_valid_header(32'h2d);
        memory[22][63:32] = 32'h2e;
        reset = 0;
        wait (fault === 1'b1);
        if (memory[4][63:32] !== DIABLO_COMPONENT_FAULT || memory[5][31:0] !== 32'd16) begin
            $display("FAIL stale slot rejection: state=%h code=%h", memory[4], memory[5]);
            $fatal(1);
        end
        $display("transport control reader checks passed");
        $finish;
    end
endmodule
