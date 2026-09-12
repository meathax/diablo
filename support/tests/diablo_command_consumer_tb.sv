`timescale 1ns/1ps
module diablo_command_consumer_tb;
    localparam [31:0] EPOCH = 32'hd1a61001;
    localparam [28:0] BASE_WORD = 29'h07fc0000;
    localparam [28:0] RECORD_CONTROL_WORD = BASE_WORD + 29'd14;
    localparam [28:0] RECORD_LAYOUT_WORD = BASE_WORD + 29'd15;
    localparam [28:0] RECORD_EPOCH_WORD = BASE_WORD + 29'd17;
    localparam [28:0] PAYLOAD_CONTROL_WORD = BASE_WORD + 29'd18;
    localparam [28:0] PAYLOAD_LAYOUT_WORD = BASE_WORD + 29'd19;
    localparam [28:0] PAYLOAD_EPOCH_WORD = BASE_WORD + 29'd21;
    localparam [28:0] RECORD_DATA_BASE_WORD = BASE_WORD + 29'h20e00;
    localparam [28:0] TARGET_PIXEL_BASE_WORD = BASE_WORD + 29'd512;
    localparam [28:0] FENCE_WORD = BASE_WORD + 29'd47;

    reg clk = 0;
    always #5 clk = ~clk;

    reg reset = 1;
    reg session_valid = 0;
    reg [31:0] session_epoch = EPOCH;
    reg [31:0] target_pixel_base = 32'h3fe01000;
    reg ddram_busy = 0;
    reg [63:0] ddram_dout = 0;
    reg ddram_dout_ready = 0;
    wire [7:0] ddram_burstcnt;
    wire [28:0] ddram_addr;
    wire ddram_rd;
    wire [63:0] ddram_din;
    wire [7:0] ddram_be;
    wire ddram_we;
    wire ring_valid;
    wire fault;
    wire [31:0] commands_executed;
    wire [31:0] commands_rejected;
    wire [63:0] last_fence;

    reg [63:0] record_memory [0:8191];
    reg [7:0] pixels [0:933887];
    reg [7:0] expected [0:933887];
    reg read_pending = 0;
    reg [28:0] read_address = 0;
    reg [2:0] read_delay = 0;
    reg [15:0] random_state = 16'h1d2b;
    reg [31:0] record_producer = 10;
    reg [31:0] record_consumer = 0;
    reg [31:0] payload_producer = 0;
    reg [31:0] payload_consumer = 0;
    reg [63:0] observed_fence = 0;
    reg write_burst_active = 0;
    reg [7:0] write_burst_remaining = 0;
    reg [7:0] write_burst_length = 0;
    reg [28:0] write_address = 0;
    integer i;
    integer mismatches;
    integer max_observed_burst;

    diablo_command_consumer #(.POLL_INTERVAL_CYCLES(2)) dut (
        .clk(clk), .reset(reset), .session_valid(session_valid), .session_epoch(session_epoch),
        .target_pixel_base(target_pixel_base), .ddram_busy(ddram_busy), .ddram_dout(ddram_dout),
        .ddram_dout_ready(ddram_dout_ready), .ddram_burstcnt(ddram_burstcnt),
        .ddram_addr(ddram_addr), .ddram_rd(ddram_rd), .ddram_din(ddram_din),
        .ddram_be(ddram_be), .ddram_we(ddram_we), .ring_valid(ring_valid), .fault(fault),
        .commands_executed(commands_executed), .commands_rejected(commands_rejected),
        .last_fence(last_fence)
    );

    function automatic [63:0] read_word(input [28:0] address);
        integer byte_base;
        begin
            if (address == RECORD_CONTROL_WORD) read_word = {record_consumer, record_producer};
            else if (address == RECORD_LAYOUT_WORD) read_word = {32'd32, 32'd2048};
            else if (address == RECORD_EPOCH_WORD) read_word = {32'd0, EPOCH};
            else if (address == PAYLOAD_CONTROL_WORD) read_word = {payload_consumer, payload_producer};
            else if (address == PAYLOAD_LAYOUT_WORD) read_word = {32'd1, 32'd196608};
            else if (address == PAYLOAD_EPOCH_WORD) read_word = {32'd0, EPOCH};
            else if (address >= RECORD_DATA_BASE_WORD && address < RECORD_DATA_BASE_WORD + 8192)
                read_word = record_memory[address - RECORD_DATA_BASE_WORD];
            else if (address >= TARGET_PIXEL_BASE_WORD && address < TARGET_PIXEL_BASE_WORD + 116736) begin
                integer slot;
                slot = (address - TARGET_PIXEL_BASE_WORD) / 38912;
                byte_base = slot * 311296 + ((address - TARGET_PIXEL_BASE_WORD) - slot * 38912) * 8;
                read_word = {pixels[byte_base + 7], pixels[byte_base + 6], pixels[byte_base + 5], pixels[byte_base + 4],
                             pixels[byte_base + 3], pixels[byte_base + 2], pixels[byte_base + 1], pixels[byte_base + 0]};
            end else read_word = 0;
        end
    endfunction

    task automatic expected_fill(input integer x, input integer y, input integer width,
                                 input integer height, input [7:0] color);
        integer xx, yy;
        begin
            for (yy = 0; yy < height; yy = yy + 1)
                for (xx = 0; xx < width; xx = xx + 1)
                    if (x + xx >= 0 && x + xx < 640 && y + yy >= 0 && y + yy < 480)
                        expected[(y + yy) * 640 + x + xx] = color;
        end
    endtask

    task automatic expected_copy(input integer dx, input integer dy, input integer width,
                                 input integer height, input integer sx, input integer sy);
        reg [7:0] temp [0:63];
        integer xx, yy, index;
        integer left, top, right, bottom, clipped_width, clipped_height;
        integer source_index, destination_index;
        begin
            left = 0; if (-dx > left) left = -dx; if (-sx > left) left = -sx;
            top = 0; if (-dy > top) top = -dy; if (-sy > top) top = -sy;
            right = width; if (640 - dx < right) right = 640 - dx; if (640 - sx < right) right = 640 - sx;
            bottom = height; if (480 - dy < bottom) bottom = 480 - dy; if (480 - sy < bottom) bottom = 480 - sy;
            clipped_width = right - left;
            clipped_height = bottom - top;
            index = 0;
            for (yy = 0; yy < clipped_height; yy = yy + 1)
                for (xx = 0; xx < clipped_width; xx = xx + 1) begin
                    source_index = (sy + top + yy) * 640 + sx + left + xx;
                    temp[index] = expected[source_index];
                    index = index + 1;
                end
            index = 0;
            for (yy = 0; yy < clipped_height; yy = yy + 1)
                for (xx = 0; xx < clipped_width; xx = xx + 1) begin
                    destination_index = (dy + top + yy) * 640 + dx + left + xx;
                    expected[destination_index] = temp[index];
                    index = index + 1;
                end
        end
    endtask

    task automatic write_record(input integer number, input [31:0] opcode, input [31:0] flags,
                                input integer x, input integer y, input integer width,
                                input integer height, input [31:0] payload_offset,
                                input [31:0] payload_bytes);
        integer base;
        begin
            base = number * 4;
            record_memory[base + 0] = {flags, opcode};
            record_memory[base + 1] = {y[31:0], x[31:0]};
            record_memory[base + 2] = {height[31:0], width[31:0]};
            record_memory[base + 3] = {payload_bytes, payload_offset};
        end
    endtask

    task automatic apply_write(input [28:0] address, input [63:0] data, input [7:0] be);
        integer byte_base;
        integer slot;
        begin
            if (address == RECORD_CONTROL_WORD && be == 8'hf0)
                record_consumer <= data[63:32];
            else if (address == PAYLOAD_CONTROL_WORD && be == 8'hf0)
                payload_consumer <= data[63:32];
            else if (address == FENCE_WORD && be == 8'hff)
                observed_fence <= data;
            else if (address >= TARGET_PIXEL_BASE_WORD && address < TARGET_PIXEL_BASE_WORD + 116736) begin
                slot = (address - TARGET_PIXEL_BASE_WORD) / 38912;
                byte_base = slot * 311296 + ((address - TARGET_PIXEL_BASE_WORD) - slot * 38912) * 8;
                for (i = 0; i < 8; i = i + 1)
                    if (be[i]) pixels[byte_base + i] <= data[i * 8 +: 8];
            end else begin
                $display("FAIL unexpected command consumer write address=%h be=%h", address, be);
                $fatal(1);
            end
        end
    endtask

    always @(posedge clk) begin
        ddram_dout_ready <= 0;
        ddram_busy <= 0;
        random_state <= {random_state[14:0], random_state[15] ^ random_state[13] ^ random_state[12] ^ random_state[10]};
        // Randomly hold the DDR endpoint busy, then return reads after a short
        // deterministic delay. This exercises every request/ack state.
        if (read_pending) begin
            if (read_delay == 0) begin
                ddram_dout <= read_word(read_address);
                ddram_dout_ready <= 1;
                read_pending <= 0;
            end else begin
                read_delay <= read_delay - 1'b1;
                ddram_busy <= 1;
            end
        end else if (ddram_rd && !ddram_busy) begin
            read_pending <= 1;
            read_address <= ddram_addr;
            read_delay <= {1'b0, random_state[1:0]} + 1'b1;
            ddram_busy <= 1;
        end else if (random_state[2:0] == 0) begin
            ddram_busy <= 1;
        end

        if (write_burst_active && (!ddram_we || ddram_burstcnt != write_burst_length))
            $fatal(1, "burst transaction was not held: active=%b we=%b count=%0d expected=%0d",
                   write_burst_active, ddram_we, ddram_burstcnt, write_burst_length);
        if (ddram_we && !ddram_busy) begin
            if (ddram_burstcnt > max_observed_burst)
                max_observed_burst = ddram_burstcnt;
            if (write_burst_active) begin
                apply_write(write_address, ddram_din, ddram_be);
                if (write_burst_remaining <= 1) begin
                    write_burst_active <= 0;
                    write_burst_remaining <= 0;
                end else begin
                    write_address <= write_address + 1'b1;
                    write_burst_remaining <= write_burst_remaining - 1'b1;
                end
            end else begin
                apply_write(ddram_addr, ddram_din, ddram_be);
                if (ddram_burstcnt > 1) begin
                    write_burst_active <= 1;
                    write_burst_length <= ddram_burstcnt;
                    write_burst_remaining <= ddram_burstcnt - 1'b1;
                    write_address <= ddram_addr + 1'b1;
                end
            end
            ddram_busy <= 1;
        end
    end

    initial begin
        for (i = 0; i < 933888; i = i + 1) begin
            pixels[i] = 0;
            expected[i] = 0;
        end
        max_observed_burst = 0;
        for (i = 0; i < 8192; i = i + 1) record_memory[i] = 0;
        write_record(0, 32'd1, 32'h0000007a, 4, 5, 3, 2, 0, 0);
        write_record(1, 32'd2, 0, 8, 5, 3, 2, 32'h00050004, 0);
        write_record(2, 32'd2, 0, 5, 5, 3, 2, 32'h00050004, 0);
        write_record(3, 32'd1, 32'h00000011, -2, -1, 5, 4, 0, 0);
        write_record(4, 32'h0000ffff, 0, 0, 0, 0, 0, 32'h11223344, 32'h55667788);
        write_record(5, 32'd1, 32'h00000155, 1, 1, 2, 2, 0, 0);
        write_record(6, 32'd1, 32'h0000003d, 16, 10, 40, 2, 0, 0);
		// Signed extremes must not wrap during RTL clipping. The first and
		// third records are fully outside; the middle one clips to row 30.
		write_record(7, 32'd1, 32'h00000044, 32'sh80000000, 0, 32'sh7fffffff, 1, 0, 0);
		write_record(8, 32'd1, 32'h0000005a, 1, 30, 32'sh7fffffff, 1, 0, 0);
		write_record(9, 32'd2, 0, 32'sh80000000, 32'sh7fffffff, 1, 1, 0, 0);
        expected_fill(4, 5, 3, 2, 8'h7a);
        expected_copy(8, 5, 3, 2, 4, 5);
        expected_copy(5, 5, 3, 2, 4, 5);
        expected_fill(-2, -1, 5, 4, 8'h11);
        expected[311296 + 640 + 1] = 8'h55;
        expected[311296 + 640 + 2] = 8'h55;
        expected[311296 + 1280 + 1] = 8'h55;
        expected[311296 + 1280 + 2] = 8'h55;
        expected_fill(16, 10, 40, 2, 8'h3d);
		expected_fill(1, 30, 639, 1, 8'h5a);
        repeat (5) @(posedge clk);
        reset <= 0;
        session_valid <= 1;
        wait (ring_valid);
        wait (commands_executed == 10);
        repeat (8) @(posedge clk);
        if (fault || commands_rejected != 2 || record_consumer != 10
            || payload_consumer != 0 || observed_fence !== 64'h1122334455667788
            || last_fence !== 64'h1122334455667788)
            $fatal(1, "command consumer status fault=%b rejected=%0d record_consumer=%0d payload_consumer=%0d fence=%h/%h",
                   fault, commands_rejected, record_consumer, payload_consumer, observed_fence, last_fence);
        if (max_observed_burst < 32)
            $fatal(1, "aligned fill did not issue the configured 32-word burst max=%0d", max_observed_burst);
        mismatches = 0;
        for (i = 0; i < 640 * 40; i = i + 1)
            if (pixels[i] !== expected[i]) begin
                if (mismatches < 8) $display("FAIL pixel index=%0d got=%h expected=%h", i, pixels[i], expected[i]);
                mismatches = mismatches + 1;
            end
        for (i = 311296; i < 311296 + 640 * 20; i = i + 1)
            if (pixels[i] !== expected[i]) mismatches = mismatches + 1;
        if (mismatches != 0) $fatal(1, "command pixels mismatched=%0d", mismatches);
        $display("command consumer randomized backpressure checks passed");
        $finish;
    end

    initial begin
        #4000000;
        $display("TIMEOUT state=%0d ring=%b fault=%b executed=%0d rejected=%0d rec_prod=%0d rec_cons=%0d target_slot=%0d", dut.state, ring_valid, fault, commands_executed, commands_rejected, dut.record_producer, dut.record_consumer, dut.target_slot);
        $fatal(1, "command consumer timeout");
    end
endmodule
