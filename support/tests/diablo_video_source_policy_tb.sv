`timescale 1ns/1ps
module diablo_video_source_policy_tb;
    reg session_valid = 0;
    reg framebuffer_valid = 0;
    reg diagnostic_video = 0;
    wire gameplay_video_valid, startup_error, vga_scaler_enable;
    wire framebuffer_enable, direct_diagnostic_enable;

    diablo_video_source_policy dut (
        .transport_session_valid(session_valid),
        .framebuffer_valid(framebuffer_valid),
        .diagnostic_video(diagnostic_video),
        .gameplay_video_valid(gameplay_video_valid),
        .startup_error(startup_error),
        .vga_scaler_enable(vga_scaler_enable),
        .framebuffer_enable(framebuffer_enable),
        .direct_diagnostic_enable(direct_diagnostic_enable)
    );

    task check_policy;
        input expected_gameplay;
        input expected_error;
        input expected_diag;
        begin
            #1;
            if (gameplay_video_valid !== expected_gameplay
             || vga_scaler_enable !== expected_gameplay
             || framebuffer_enable !== expected_gameplay
             || startup_error !== expected_error
             || direct_diagnostic_enable !== expected_diag)
                $fatal(1, "source policy mismatch: gameplay=%b scaler=%b fb=%b error=%b diag=%b",
                       gameplay_video_valid, vga_scaler_enable, framebuffer_enable,
                       startup_error, direct_diagnostic_enable);
        end
    endtask

    initial begin
        // Before attachment, direct output is the visible startup/error state.
        check_policy(0, 1, 0);
        // A session without a complete frame remains startup/error, never stale FB.
        session_valid = 1; check_policy(0, 1, 0);
        // A complete indexed frame enables both framework paths atomically.
        framebuffer_valid = 1; check_policy(1, 0, 0);
        // Diagnostics wins explicitly and disables gameplay advertisement.
        diagnostic_video = 1; check_policy(0, 0, 1);
        // Returning to gameplay requires a valid frame again.
        diagnostic_video = 0; framebuffer_valid = 0; check_policy(0, 1, 0);
        $display("PASS: video source policy prevents diagnostic/gameplay mux aliasing");
        $finish;
    end
endmodule
