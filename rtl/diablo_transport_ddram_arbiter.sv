// SPDX-License-Identifier: GPL-2.0-or-later
// Single 64-bit core-DDR port arbiter. The scaler's framebuffer port is separate.
module diablo_transport_ddram_arbiter #(
    // A fault is fail-stop: transactions do not resume until the transport
    // supervisor has reset the arbiter.  This makes a permanently busy DDR
    // interface observable without ever handing a possible late read reply
    // to another client.
    parameter [15:0] READ_RESPONSE_TIMEOUT_CYCLES = 16'd1024,
    parameter [15:0] BUSY_TIMEOUT_CYCLES = 16'd1024
) (
    input wire clk,
    input wire reset,
    input wire session_valid,

    input wire [7:0] control_burstcnt,
    input wire [28:0] control_addr,
    input wire control_rd,
    input wire [63:0] control_din,
    input wire [7:0] control_be,
    input wire control_we,
    output reg control_busy,
    output reg [63:0] control_dout,
    output reg control_dout_ready,

    input wire [7:0] frame_burstcnt,
    input wire [28:0] frame_addr,
    input wire frame_rd,
    input wire [63:0] frame_din,
    input wire [7:0] frame_be,
    input wire frame_we,
    output reg frame_busy,
    output reg [63:0] frame_dout,
    output reg frame_dout_ready,

    input wire [7:0] audio_burstcnt,
    input wire [28:0] audio_addr,
    input wire audio_rd,
    input wire [63:0] audio_din,
    input wire [7:0] audio_be,
    input wire audio_we,
    output reg audio_busy,
    output reg [63:0] audio_dout,
    output reg audio_dout_ready,

    input wire [7:0] input_burstcnt,
    input wire [28:0] input_addr,
    input wire input_rd,
    input wire [63:0] input_din,
    input wire [7:0] input_be,
    input wire input_we,
    output reg input_busy,
    output reg [63:0] input_dout,
    output reg input_dout_ready,

    input wire [7:0] command_burstcnt,
    input wire [28:0] command_addr,
    input wire command_rd,
    input wire [63:0] command_din,
    input wire [7:0] command_be,
    input wire command_we,
    output reg command_busy,
    output reg [63:0] command_dout,
    output reg command_dout_ready,

    input wire ddram_busy,
    input wire [63:0] ddram_dout,
    input wire ddram_dout_ready,
    output reg [7:0] ddram_burstcnt,
    output reg [28:0] ddram_addr,
    output reg ddram_rd,
    output reg [63:0] ddram_din,
    output reg [7:0] ddram_be,
    output reg ddram_we,
    output reg fault = 1'b0,
    // Read-only pre-edge arbitration state for bounded PCM event capture.
    output wire [63:0] diagnostic
);
    // A zero timeout is a legal parameter value in some generated builds. It
    // must mean the smallest observable one-cycle deadline, rather than
    // underflowing the comparison threshold to 16'hffff and disabling the
    // watchdog for nearly an entire counter wrap.
    localparam [15:0] READ_RESPONSE_TIMEOUT_LIMIT =
        (READ_RESPONSE_TIMEOUT_CYCLES == 0) ? 16'd1 : READ_RESPONSE_TIMEOUT_CYCLES;
    localparam [15:0] BUSY_TIMEOUT_LIMIT =
        (BUSY_TIMEOUT_CYCLES == 0) ? 16'd1 : BUSY_TIMEOUT_CYCLES;
    localparam [1:0] OWNER_CONTROL = 2'd0;
    localparam [1:0] OWNER_FRAME = 2'd1;
    localparam [1:0] OWNER_AUDIO = 2'd2;
    localparam [1:0] OWNER_INPUT = 2'd3;
    localparam [2:0] OWNER_COMMAND = 3'd4;

    reg read_pending = 1'b0;
    reg [2:0] read_owner = OWNER_CONTROL;
    // Avalon burst transactions must retain their owner until every beat has
    // been accepted.  Without this lock a newly asserted audio/input/frame
    // request could switch the mux in the middle of a command FillRect burst.
    reg burst_lock = 1'b0;
    reg [2:0] burst_owner = OWNER_CONTROL;
    reg [7:0] burst_remaining = 0;
    // A continuously non-empty PCM ring used to make the strict ordering below
    // starve command verification/rendering forever.  Keep audio/input/frame
    // latency priority, but reserve one accepted transaction for a pending
    // command after a bounded run of seven higher-priority grants.  Read
    // responses and write bursts remain locked to their original owner.
    localparam [3:0] MAX_HIGH_PRIORITY_GRANTS = 4'd7;
    reg [3:0] command_wait_grants = 0;
    reg [15:0] read_response_wait = 0;
    reg [15:0] busy_wait = 0;
    wire command_pending = command_rd || command_we;
    wire force_command_service = session_valid && command_pending
                              && command_wait_grants >= MAX_HIGH_PRIORITY_GRANTS;
    wire [2:0] priority_owner = !session_valid ? OWNER_CONTROL
                               // Sparse session checks must not depend on an idle
                               // audio/frame/command port. A missed epoch change
                               // otherwise leaves the old session attached forever.
                               // Existing read and burst locks still take precedence.
                               : (control_rd || control_we) ? OWNER_CONTROL
                               : force_command_service ? OWNER_COMMAND
                               // Audio has priority after attachment. It is buffered and
                               // acknowledged in batches, so this protects its deadline
                               // without monopolising DDR. Input and frame metadata remain
                               // ahead of command rendering so a busy renderer cannot hide
                               // user edges or miss a vblank handoff.
                               : (audio_rd || audio_we) ? OWNER_AUDIO
                               : (input_rd || input_we) ? OWNER_INPUT
                               : (frame_rd || frame_we) ? OWNER_FRAME
                               : (command_rd || command_we) ? OWNER_COMMAND
                               : OWNER_CONTROL;
    wire [2:0] selected_owner = burst_lock ? burst_owner
                               : read_pending ? read_owner
                               : priority_owner;
    // [2:0] selected owner, then the pending/lock/owner/counter fields in
    // increasing bit order. This is sampled by the player only on starvation.
    assign diagnostic = {2'b00, force_command_service, audio_busy, fault,
                         audio_we, audio_rd, ddram_dout_ready, ddram_busy,
                         command_wait_grants, busy_wait, read_response_wait,
                         burst_remaining, burst_owner, read_owner, burst_lock,
                         read_pending, selected_owner};

    always @* begin
        ddram_burstcnt = 0;
        ddram_addr = 0;
        ddram_rd = 1'b0;
        ddram_din = 0;
        ddram_be = 0;
        ddram_we = 1'b0;

        control_busy = 1'b1;
        control_dout = 0;
        control_dout_ready = 1'b0;
        frame_busy = 1'b1;
        frame_dout = 0;
        frame_dout_ready = 1'b0;
        audio_busy = 1'b1;
        audio_dout = 0;
        audio_dout_ready = 1'b0;
        input_busy = 1'b1;
        input_dout = 0;
        input_dout_ready = 1'b0;
        command_busy = 1'b1;
        command_dout = 0;
        command_dout_ready = 1'b0;

        if (!reset && fault) begin
            // A physical read can still answer after its timeout.  Leave all
            // requesters backpressured, but drain that one reply through the
            // recorded owner so it cannot be consumed by a later client.
            if (read_pending) begin
                case (read_owner)
                    OWNER_CONTROL: begin
                        control_dout = ddram_dout;
                        control_dout_ready = ddram_dout_ready;
                    end
                    OWNER_FRAME: begin
                        frame_dout = ddram_dout;
                        frame_dout_ready = ddram_dout_ready;
                    end
                    OWNER_AUDIO: begin
                        audio_dout = ddram_dout;
                        audio_dout_ready = ddram_dout_ready;
                    end
                    OWNER_INPUT: begin
                        input_dout = ddram_dout;
                        input_dout_ready = ddram_dout_ready;
                    end
                    default: begin
                        command_dout = ddram_dout;
                        command_dout_ready = ddram_dout_ready;
                    end
                endcase
            end
        end else if (!reset) begin
        case (selected_owner)
            OWNER_CONTROL: begin
                ddram_burstcnt = control_burstcnt;
                ddram_addr = control_addr;
                ddram_rd = control_rd;
                ddram_din = control_din;
                ddram_be = control_be;
                ddram_we = control_we;
                control_busy = ddram_busy;
                control_dout = ddram_dout;
                control_dout_ready = ddram_dout_ready;
            end
            OWNER_FRAME: begin
                ddram_burstcnt = frame_burstcnt;
                ddram_addr = frame_addr;
                ddram_rd = frame_rd;
                ddram_din = frame_din;
                ddram_be = frame_be;
                ddram_we = frame_we;
                frame_busy = ddram_busy;
                frame_dout = ddram_dout;
                frame_dout_ready = ddram_dout_ready;
            end
            OWNER_AUDIO: begin
                ddram_burstcnt = audio_burstcnt;
                ddram_addr = audio_addr;
                ddram_rd = audio_rd;
                ddram_din = audio_din;
                ddram_be = audio_be;
                ddram_we = audio_we;
                audio_busy = ddram_busy;
                audio_dout = ddram_dout;
                audio_dout_ready = ddram_dout_ready;
            end
            default: begin
                if (selected_owner == OWNER_INPUT) begin
                    ddram_burstcnt = input_burstcnt;
                    ddram_addr = input_addr;
                    ddram_rd = input_rd;
                    ddram_din = input_din;
                    ddram_be = input_be;
                    ddram_we = input_we;
                    input_busy = ddram_busy;
                    input_dout = ddram_dout;
                    input_dout_ready = ddram_dout_ready;
                end else begin
                    ddram_burstcnt = command_burstcnt;
                    ddram_addr = command_addr;
                    ddram_rd = command_rd;
                    ddram_din = command_din;
                    ddram_be = command_be;
                    ddram_we = command_we;
                    command_busy = ddram_busy;
                    command_dout = ddram_dout;
                    command_dout_ready = ddram_dout_ready;
                end
            end
        endcase
        end
    end

    always @(posedge clk) begin
        if (reset) begin
            read_pending <= 1'b0;
            read_owner <= OWNER_CONTROL;
            burst_lock <= 1'b0;
            burst_owner <= OWNER_CONTROL;
            burst_remaining <= 0;
            command_wait_grants <= 0;
            read_response_wait <= 0;
            busy_wait <= 0;
            fault <= 1'b0;
        end else begin
            if (!fault && burst_lock) begin
                if (ddram_we && !ddram_busy) begin
                    if (burst_remaining <= 1) begin
                        burst_lock <= 1'b0;
                        burst_remaining <= 0;
                    end else begin
                        burst_remaining <= burst_remaining - 1'b1;
                    end
                end
            end else if (ddram_we && !ddram_busy && ddram_burstcnt > 1) begin
                burst_lock <= 1'b1;
                burst_owner <= selected_owner;
                burst_remaining <= ddram_burstcnt - 1'b1;
            end

            if (read_pending) begin
                if (ddram_dout_ready) begin
                    read_pending <= 1'b0;
                    read_response_wait <= 0;
                end else if (!fault) begin
                    if (read_response_wait >= READ_RESPONSE_TIMEOUT_LIMIT - 1'b1)
                        fault <= 1'b1;
                    else
                        read_response_wait <= read_response_wait + 1'b1;
                end
            end else if (!fault && ddram_rd && !ddram_busy) begin
                read_pending <= 1'b1;
                read_owner <= selected_owner;
                read_response_wait <= 0;
            end else begin
                read_response_wait <= 0;
            end

            // ddram_busy can remain asserted before any request is accepted.
            // Latch the same fail-stop fault after a bounded wait; there is no
            // outstanding read in this case, so no late response is possible.
            if (!fault && session_valid && !read_pending && (ddram_rd || ddram_we) && ddram_busy) begin
                if (busy_wait >= BUSY_TIMEOUT_LIMIT - 1'b1)
                    fault <= 1'b1;
                else
                    busy_wait <= busy_wait + 1'b1;
            end else begin
                busy_wait <= 0;
            end

            // Count only accepted, owner-unlocked transactions. A delayed
            // response cannot inflate the age, and a command burst resets the
            // reservation only once its first beat is accepted.
            if (fault || !session_valid || !command_pending) begin
                command_wait_grants <= 0;
            end else if (!burst_lock && !read_pending && (ddram_rd || ddram_we) && !ddram_busy) begin
                if (selected_owner == OWNER_COMMAND)
                    command_wait_grants <= 0;
                else if (command_wait_grants < MAX_HIGH_PRIORITY_GRANTS)
                    command_wait_grants <= command_wait_grants + 1'b1;
            end
        end
    end
endmodule
