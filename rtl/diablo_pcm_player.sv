// SPDX-License-Identifier: GPL-2.0-or-later
// Bounded ARM-produced S16 stereo PCM ring consumer for the MiSTer core port.
module diablo_pcm_player #(
    parameter integer SAMPLE_DIVISOR = 1050,      // 50.4 MHz / 48 kHz
    parameter integer POLL_INTERVAL_CYCLES = 50400,
    // Aulib's MiSTer callback is intentionally serviced in bounded chunks.
    // Keep enough local audio to cover one callback plus DDR arbitration jitter;
    // 1,024 samples was shorter than the observed ARM callback interval.
    parameter integer PRIME_SAMPLES = 1024,
    parameter integer ACK_BATCH = 32,
    parameter integer FIFO_SAMPLES = 4096
) (
    input wire clk,
    input wire reset,
    input wire session_valid,
    input wire [31:0] session_epoch,
    // A pre-edge arbitration sample, captured only on the first active
    // starvation edge. It is diagnostic-only and cannot affect scheduling.
    input wire [63:0] arbiter_diagnostic,

    input wire ddram_busy,
    input wire [63:0] ddram_dout,
    input wire ddram_dout_ready,
    output wire [7:0] ddram_burstcnt,
    output wire [28:0] ddram_addr,
    output wire ddram_rd,
    output wire [63:0] ddram_din,
    output wire [7:0] ddram_be,
    output wire ddram_we,

    output reg [15:0] audio_l = 0,
    output reg [15:0] audio_r = 0,
    output reg [31:0] underrun_count = 0,
    output reg [31:0] resync_count = 0,
    output reg [$clog2(FIFO_SAMPLES):0] queue_depth = 0,
    output reg ring_valid = 1'b0
);
    `include "diablo_transport_abi.svh"

    localparam [28:0] SHARED_BASE_WORD = 29'h07fc0000;
    localparam [28:0] PCM_CONTROL_WORD = SHARED_BASE_WORD + 29'd10;
    localparam [28:0] PCM_LAYOUT_WORD = SHARED_BASE_WORD + 29'd11;
    localparam [28:0] PCM_STATUS_WORD = SHARED_BASE_WORD + 29'd12;
    localparam [28:0] PCM_EPOCH_WORD = SHARED_BASE_WORD + 29'd13;
    localparam [28:0] PCM_UNDERFLOW_SNAPSHOT_WORD = SHARED_BASE_WORD
                                        + (DIABLO_TRANSPORT_PCM_UNDERFLOW_SNAPSHOT_OFFSET >> 3);
    localparam [28:0] PCM_DATA_BASE_WORD = SHARED_BASE_WORD
                                              + (DIABLO_TRANSPORT_PCM_REGION_OFFSET >> 3);
    // Clamp zero-valued timing parameters so simulation and constrained builds
    // do not turn the intended immediate cadence into a 16-bit underflow.
    localparam integer SAMPLE_DIVISOR_LIMIT =
        (SAMPLE_DIVISOR <= 0) ? 1 : SAMPLE_DIVISOR;
    localparam integer POLL_INTERVAL_LIMIT =
        (POLL_INTERVAL_CYCLES <= 0) ? 1 : POLL_INTERVAL_CYCLES;
    localparam [4:0] INACTIVE = 5'd0;
    localparam [4:0] VERIFY_REQUEST = 5'd1;
    localparam [4:0] VERIFY_WAIT = 5'd2;
    localparam [4:0] FILL_CHECK = 5'd3;
    localparam [4:0] SAMPLE_REQUEST = 5'd4;
    localparam [4:0] SAMPLE_WAIT = 5'd5;
    localparam [4:0] SAMPLE_STORE_SECOND = 5'd6;
    localparam [4:0] ACK_REQUEST = 5'd7;
    localparam [4:0] WAIT_PRODUCER = 5'd8;
    localparam [4:0] WAIT_REVERIFY = 5'd9;
    localparam [4:0] STATUS_REQUEST = 5'd10;
    localparam [4:0] QUEUE_STATUS_REQUEST = 5'd11;
    // The commit clear makes a replacement snapshot a real bounded seqlock:
    // readers cannot accept a previous nonzero commit alongside new payload.
    localparam [4:0] TRACE_CLEAR_COMMIT_REQUEST = 5'd12;
    localparam [4:0] TRACE_WORD0_REQUEST = 5'd13;
    localparam [4:0] TRACE_WORD1_REQUEST = 5'd14;
    localparam [4:0] TRACE_WORD2_REQUEST = 5'd15;
    localparam [4:0] TRACE_WORD3_REQUEST = 5'd16;
    localparam [4:0] TRACE_WORD4_REQUEST = 5'd17;
    localparam [4:0] TRACE_COMMIT_REQUEST = 5'd18;
    localparam integer FIFO_ADDR_BITS = $clog2(FIFO_SAMPLES);

    reg [4:0] state = INACTIVE;
    reg [1:0] verify_index = 0;
    reg layout_valid = 1'b0;
    reg [31:0] active_epoch = 0;
    reg [31:0] producer_sequence = 0;
    reg [31:0] fetch_sequence = 0;
    reg [31:0] published_consumer = 0;
    reg fetch_pair = 1'b0;
    reg [15:0] deferred_left = 0;
    reg [15:0] deferred_right = 0;
    reg [15:0] sample_divider = 0;
    reg [15:0] poll_counter = 0;
    reg status_to_verify = 1'b0;
    reg playback_running = 1'b0;
    reg playback_started = 1'b0;
    reg starvation_active = 1'b0;
    reg [31:0] event_cycle = 0;
    // A reset can reattach to the same ARM epoch. Invalidate the DDR commit
    // before that session can expose a pre-reset event as current evidence.
    reg trace_invalidate_pending = 1'b1;
    reg trace_pending = 1'b0;
    reg [31:0] trace_commit_sequence = 0;
    reg [31:0] trace_event_cycle = 0;
    reg [31:0] trace_epoch = 0;
    reg [31:0] trace_producer_sequence = 0;
    reg [31:0] trace_fetch_sequence = 0;
    reg [31:0] trace_published_consumer = 0;
    reg [31:0] trace_underrun_count = 0;
    reg [31:0] trace_queue_depth = 0;
    reg [31:0] trace_player_state = 0;
    reg [63:0] trace_arbiter_diagnostic = 0;
    reg [31:0] trace_resync_count = 0;

    (* ramstyle = "M10K" *) reg [31:0] fifo [0:FIFO_SAMPLES - 1];
    reg [FIFO_ADDR_BITS - 1:0] fifo_read_pointer = 0;
    reg [FIFO_ADDR_BITS - 1:0] fifo_write_pointer = 0;

    wire sample_tick = (sample_divider == SAMPLE_DIVISOR_LIMIT - 1);
    wire [31:0] available_samples = producer_sequence - fetch_sequence;
    wire [31:0] unacknowledged_samples = fetch_sequence - published_consumer;
    wire sample_fetch_complete = (state == SAMPLE_WAIT) && ddram_dout_ready;
    wire sample_store_second = (state == SAMPLE_STORE_SECOND);
    wire fifo_push = sample_fetch_complete || sample_store_second;
    wire playback_pop = sample_tick && playback_running && (queue_depth != 0);

    function automatic [28:0] pcm_data_address(input [31:0] sample_sequence);
        begin
            // 32768 four-byte records: two complete stereo records per
            // 64-bit DDR word. The lower 15 bits select the ring position.
            pcm_data_address = PCM_DATA_BASE_WORD + sample_sequence[14:1];
        end
    endfunction

    assign ddram_burstcnt = 8'd1;
    assign ddram_rd = (state == VERIFY_REQUEST) || (state == SAMPLE_REQUEST);
    assign ddram_we = (state == ACK_REQUEST) || (state == STATUS_REQUEST)
                    || (state == QUEUE_STATUS_REQUEST)
                    || (state == TRACE_CLEAR_COMMIT_REQUEST)
                    || (state == TRACE_WORD0_REQUEST)
                    || (state == TRACE_WORD1_REQUEST)
                    || (state == TRACE_WORD2_REQUEST)
                    || (state == TRACE_WORD3_REQUEST)
                    || (state == TRACE_WORD4_REQUEST)
                    || (state == TRACE_COMMIT_REQUEST);
    assign ddram_addr = (state == VERIFY_REQUEST)
                      ? ((verify_index == 0) ? PCM_CONTROL_WORD
                       : (verify_index == 1) ? PCM_LAYOUT_WORD : PCM_EPOCH_WORD)
                       : (state == SAMPLE_REQUEST) ? pcm_data_address(fetch_sequence)
                        : (state == STATUS_REQUEST) ? PCM_STATUS_WORD
                        : (state == QUEUE_STATUS_REQUEST) ? PCM_EPOCH_WORD
                        : (state == TRACE_WORD1_REQUEST) ? PCM_UNDERFLOW_SNAPSHOT_WORD + 1'b1
                        : (state == TRACE_WORD2_REQUEST) ? PCM_UNDERFLOW_SNAPSHOT_WORD + 2'd2
                        : (state == TRACE_WORD3_REQUEST) ? PCM_UNDERFLOW_SNAPSHOT_WORD + 2'd3
                        : (state == TRACE_WORD4_REQUEST) ? PCM_UNDERFLOW_SNAPSHOT_WORD + 3'd4
                        : (state == TRACE_CLEAR_COMMIT_REQUEST || state == TRACE_COMMIT_REQUEST)
                        ? PCM_UNDERFLOW_SNAPSHOT_WORD + 3'd5
                        : (state == TRACE_WORD0_REQUEST) ? PCM_UNDERFLOW_SNAPSHOT_WORD
                        : PCM_CONTROL_WORD;
    // The ARM owns the producer cursor in the low half of PCM_CONTROL_WORD.
    // PCM_STATUS_WORD is FPGA-owned and publishes underrun/resync counters as
    // {resync_count, underrun_count}; the ARM only reads this diagnostic word.
    assign ddram_din = (state == STATUS_REQUEST)
                      ? {resync_count, underrun_count}
                      : (state == QUEUE_STATUS_REQUEST)
                      ? {{(32-$bits(queue_depth)){1'b0}}, queue_depth, active_epoch}
                      : (state == TRACE_CLEAR_COMMIT_REQUEST) ? 64'd0
                      : (state == TRACE_WORD0_REQUEST) ? {trace_epoch, trace_event_cycle}
                      : (state == TRACE_WORD1_REQUEST) ? {trace_fetch_sequence, trace_producer_sequence}
                      : (state == TRACE_WORD2_REQUEST) ? {trace_underrun_count, trace_published_consumer}
                      : (state == TRACE_WORD3_REQUEST) ? {trace_player_state, trace_queue_depth}
                      : (state == TRACE_WORD4_REQUEST) ? trace_arbiter_diagnostic
                      : (state == TRACE_COMMIT_REQUEST) ? {trace_commit_sequence, trace_resync_count}
                      : {fetch_sequence, 32'd0};
    // ARM owns producer_sequence in the low half. FPGA publishes only the
    // high consumer_sequence half, in bounded batches after local buffering.
    assign ddram_be = (state == STATUS_REQUEST || state == QUEUE_STATUS_REQUEST
                    || state == TRACE_CLEAR_COMMIT_REQUEST || state == TRACE_WORD0_REQUEST
                    || state == TRACE_WORD1_REQUEST || state == TRACE_WORD2_REQUEST
                    || state == TRACE_WORD3_REQUEST || state == TRACE_WORD4_REQUEST
                    || state == TRACE_COMMIT_REQUEST)
                     ? 8'hff : 8'hf0;

    always @(posedge clk) begin
        if (reset || !session_valid) begin
            state <= INACTIVE;
            verify_index <= 0;
            layout_valid <= 1'b0;
            active_epoch <= 0;
            producer_sequence <= 0;
            fetch_sequence <= 0;
            published_consumer <= 0;
            fetch_pair <= 1'b0;
            deferred_left <= 0;
            deferred_right <= 0;
            sample_divider <= 0;
            poll_counter <= 0;
            status_to_verify <= 1'b0;
            playback_running <= 1'b0;
            playback_started <= 1'b0;
            starvation_active <= 1'b0;
            event_cycle <= 0;
            trace_invalidate_pending <= 1'b1;
            trace_pending <= 1'b0;
            trace_commit_sequence <= 0;
            trace_event_cycle <= 0;
            trace_epoch <= 0;
            trace_producer_sequence <= 0;
            trace_fetch_sequence <= 0;
            trace_published_consumer <= 0;
            trace_underrun_count <= 0;
            trace_queue_depth <= 0;
            trace_player_state <= 0;
            trace_arbiter_diagnostic <= 0;
            trace_resync_count <= 0;
            fifo_read_pointer <= 0;
            fifo_write_pointer <= 0;
            queue_depth <= 0;
            audio_l <= 0;
            audio_r <= 0;
            underrun_count <= 0;
            resync_count <= 0;
            ring_valid <= 1'b0;
        end else begin
            event_cycle <= event_cycle + 1'b1;
            if (sample_tick) sample_divider <= 0;
            else sample_divider <= sample_divider + 1'b1;

            if (active_epoch != session_epoch) begin
                state <= VERIFY_REQUEST;
                verify_index <= 0;
                layout_valid <= 1'b0;
                active_epoch <= session_epoch;
                producer_sequence <= 0;
                fetch_sequence <= 0;
                published_consumer <= 0;
                fetch_pair <= 1'b0;
                deferred_left <= 0;
                deferred_right <= 0;
                poll_counter <= 0;
                status_to_verify <= 1'b0;
                playback_running <= 1'b0;
                playback_started <= 1'b0;
                starvation_active <= 1'b0;
                trace_invalidate_pending <= 1'b1;
                trace_pending <= 1'b0;
                trace_commit_sequence <= 0;
                fifo_read_pointer <= 0;
                fifo_write_pointer <= 0;
                queue_depth <= 0;
                audio_l <= 0;
                audio_r <= 0;
                ring_valid <= 1'b0;
            end else begin
                if (sample_fetch_complete) begin
                    if (fetch_pair) begin
                        fifo[fifo_write_pointer] <= ddram_dout[31:0];
                        deferred_left <= ddram_dout[47:32];
                        deferred_right <= ddram_dout[63:48];
                    end else begin
                        fifo[fifo_write_pointer] <= fetch_sequence[0] ? ddram_dout[63:32]
                                                                     : ddram_dout[31:0];
                    end
                    fifo_write_pointer <= fifo_write_pointer + 1'b1;
                    fetch_sequence <= fetch_sequence + 1'b1;
                end else if (sample_store_second) begin
                    fifo[fifo_write_pointer] <= {deferred_right, deferred_left};
                    fifo_write_pointer <= fifo_write_pointer + 1'b1;
                    fetch_sequence <= fetch_sequence + 1'b1;
                end

                if (playback_pop) begin
                    audio_l <= fifo[fifo_read_pointer][15:0];
                    audio_r <= fifo[fifo_read_pointer][31:16];
                    fifo_read_pointer <= fifo_read_pointer + 1'b1;
                end else if (sample_tick) begin
                    audio_l <= 0;
                    audio_r <= 0;
                    if (playback_started) underrun_count <= underrun_count + 1'b1;
                end

                case ({fifo_push, playback_pop})
                    2'b10: queue_depth <= queue_depth + 1'b1;
                    2'b01: queue_depth <= queue_depth - 1'b1;
                    2'b11: queue_depth <= queue_depth;
                    default: queue_depth <= queue_depth;
                endcase

                if (!playback_running
                 && (queue_depth + (fifo_push ? 1'b1 : 1'b0) >= PRIME_SAMPLES)) begin
                    playback_running <= 1'b1;
                    playback_started <= 1'b1;
                    starvation_active <= 1'b0;
                end else if (playback_pop && queue_depth == 1 && !fifo_push) begin
                    playback_running <= 1'b0;
                end

                // underrun_count remains a per-empty-output-tick counter. The
                // event record is deliberately separate and latches only the
                // first active starvation edge until playback starts again.
                if (playback_started && sample_tick && queue_depth == 0 && !starvation_active) begin
                    starvation_active <= 1'b1;
                    trace_pending <= 1'b1;
                    trace_event_cycle <= event_cycle;
                    trace_epoch <= active_epoch;
                    trace_producer_sequence <= producer_sequence;
                    trace_fetch_sequence <= fetch_sequence;
                    trace_published_consumer <= published_consumer;
                    trace_underrun_count <= underrun_count + 1'b1;
                    trace_queue_depth <= {{(32-$bits(queue_depth)){1'b0}}, queue_depth};
                    trace_player_state <= {21'd0, fetch_pair, status_to_verify, layout_valid,
                                           ring_valid, playback_started, playback_running, state};
                    trace_arbiter_diagnostic <= arbiter_diagnostic;
                    trace_resync_count <= resync_count;
                    trace_commit_sequence <= (trace_commit_sequence == 32'hffffffff)
                                           ? 32'd1 : trace_commit_sequence + 1'b1;
                end

                case (state)
                    INACTIVE: begin
                        state <= VERIFY_REQUEST;
                        verify_index <= 0;
                    end
                    VERIFY_REQUEST: if (!ddram_busy) state <= VERIFY_WAIT;
                    VERIFY_WAIT: if (ddram_dout_ready) begin
                        case (verify_index)
                            0: begin
                                producer_sequence <= ddram_dout[31:0];
                                // The ARM producer may be polled while samples
                                // are already prefetched into local RAM. The
                                // FPGA-owned consumer is authoritative for the
                                // local cursors; reloading it here would rewind
                                // fetch_sequence on every periodic poll and
                                // replay the tail of the ring. Cursors are
                                // initialized on a new epoch and reset only
                                // by the explicit overrun path below.
                                if (!ring_valid) begin
                                    fetch_sequence <= ddram_dout[63:32];
                                    published_consumer <= ddram_dout[63:32];
                                end
                            end
                            1: layout_valid <= (ddram_dout[31:0] == DIABLO_TRANSPORT_PCM_CAPACITY)
                                             && (ddram_dout[63:32] == DIABLO_TRANSPORT_PCM_RECORD_BYTES);
                            default: begin
                                if (layout_valid && ddram_dout[31:0] == active_epoch) begin
                                    ring_valid <= 1'b1;
                                    state <= FILL_CHECK;
                                end else begin
                                    ring_valid <= 1'b0;
                                    poll_counter <= 0;
                                    state <= WAIT_REVERIFY;
                                end
                            end
                        endcase
                        if (verify_index != 2) begin
                            verify_index <= verify_index + 1'b1;
                            state <= VERIFY_REQUEST;
                        end
                    end
                    FILL_CHECK: begin
                        if (!ring_valid) begin
                            poll_counter <= 0;
                            state <= WAIT_REVERIFY;
                        end else if (trace_invalidate_pending) begin
                            // This one full-word clear is the reset/epoch
                            // ownership boundary. It is not a playback-timing
                            // operation and occurs only before a reattached
                            // session can publish a new event.
                            state <= TRACE_CLEAR_COMMIT_REQUEST;
                        end else if (available_samples > DIABLO_TRANSPORT_PCM_CAPACITY) begin
                            // A producer reset or overrun invalidates local
                            // sequencing. Drop local data and validate anew.
                            queue_depth <= 0;
                            playback_running <= 1'b0;
                            ring_valid <= 1'b0;
                            resync_count <= resync_count + 1'b1;
                            poll_counter <= 0;
                            state <= WAIT_REVERIFY;
                end else if (available_samples != 0 && queue_depth != FIFO_SAMPLES) begin
                    fetch_pair <= !fetch_sequence[0] && available_samples >= 2
                                       && queue_depth <= FIFO_SAMPLES - 2;
                            state <= SAMPLE_REQUEST;
                        end else if (unacknowledged_samples >= ACK_BATCH
                                  || (available_samples == 0 && unacknowledged_samples != 0)) begin
                            // Flush a final partial batch when the producer is
                            // caught up. Without this edge-triggered flush a
                            // short tail (for example seven records after a
                            // 32-record batch) would remain permanently
                            // invisible to the ARM producer.
                            state <= ACK_REQUEST;
                        end else if (trace_pending) begin
                            // Preserve source-first behavior: a pending PCM word
                            // is fetched above before this diagnostic is exported.
                            state <= TRACE_CLEAR_COMMIT_REQUEST;
                        end else begin
                            poll_counter <= 0;
                            state <= WAIT_PRODUCER;
                        end
                    end
                    SAMPLE_REQUEST: if (!ddram_busy) state <= SAMPLE_WAIT;
                    SAMPLE_WAIT: if (ddram_dout_ready) begin
                        if (fetch_pair) state <= SAMPLE_STORE_SECOND;
                        else state <= FILL_CHECK;
                    end
                    SAMPLE_STORE_SECOND: state <= FILL_CHECK;
                    ACK_REQUEST: if (!ddram_busy) begin
                        published_consumer <= fetch_sequence;
                        status_to_verify <= 1'b0;
                        state <= STATUS_REQUEST;
                    end
                    STATUS_REQUEST: if (!ddram_busy) begin
                        state <= QUEUE_STATUS_REQUEST;
                    end
                    QUEUE_STATUS_REQUEST: if (!ddram_busy) begin
                        poll_counter <= 0;
                        if (status_to_verify) begin
                            verify_index <= 0;
                            state <= VERIFY_REQUEST;
                        end else begin
                            state <= FILL_CHECK;
                        end
                    end
                    TRACE_CLEAR_COMMIT_REQUEST: if (!ddram_busy) begin
                        trace_invalidate_pending <= 1'b0;
                        if (trace_pending) state <= TRACE_WORD0_REQUEST;
                        else state <= FILL_CHECK;
                    end
                    TRACE_WORD0_REQUEST: if (!ddram_busy)
                        state <= TRACE_WORD1_REQUEST;
                    TRACE_WORD1_REQUEST: if (!ddram_busy)
                        state <= TRACE_WORD2_REQUEST;
                    TRACE_WORD2_REQUEST: if (!ddram_busy)
                        state <= TRACE_WORD3_REQUEST;
                    TRACE_WORD3_REQUEST: if (!ddram_busy)
                        state <= TRACE_WORD4_REQUEST;
                    TRACE_WORD4_REQUEST: if (!ddram_busy)
                        state <= TRACE_COMMIT_REQUEST;
                    TRACE_COMMIT_REQUEST: if (!ddram_busy) begin
                        trace_pending <= 1'b0;
                        state <= FILL_CHECK;
                    end
                    WAIT_PRODUCER: begin
                        if (trace_invalidate_pending || trace_pending) begin
                            state <= TRACE_CLEAR_COMMIT_REQUEST;
                        end else if (poll_counter == POLL_INTERVAL_LIMIT - 1) begin
                            poll_counter <= 0;
                            status_to_verify <= 1'b1;
                            state <= STATUS_REQUEST;
                        end else poll_counter <= poll_counter + 1'b1;
                    end
                    WAIT_REVERIFY: begin
                        if (trace_invalidate_pending || trace_pending) begin
                            state <= TRACE_CLEAR_COMMIT_REQUEST;
                        end else if (poll_counter == POLL_INTERVAL_LIMIT - 1) begin
                            poll_counter <= 0;
                            state <= VERIFY_REQUEST;
                            verify_index <= 0;
                        end else poll_counter <= poll_counter + 1'b1;
                    end
                    default: state <= INACTIVE;
                endcase
            end
        end
    end
endmodule
