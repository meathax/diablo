// Single source-of-truth for the core-side gameplay/diagnostic video choice.
// The MiSTer framework owns the final connector mux; this module only decides
// when the indexed framebuffer is allowed to advertise itself and what the
// direct RGB diagnostic generator must show while it is not.
module diablo_video_source_policy (
    input  wire transport_session_valid,
    input  wire framebuffer_valid,
    input  wire diagnostic_video,
    output wire gameplay_video_valid,
    output wire startup_error,
    output wire vga_scaler_enable,
    output wire framebuffer_enable,
    output wire direct_diagnostic_enable
);
    // A complete frame is required before either FB_EN or VGA_SCALER can be
    // asserted.  framebuffer_blank is deliberately handled by FB_FORCE_BLANK
    // in the scanout module so palette staging cannot expose mixed pixels.
    assign gameplay_video_valid = transport_session_valid
                                && framebuffer_valid
                                && !diagnostic_video;
    assign startup_error = !diagnostic_video && !gameplay_video_valid;
    assign vga_scaler_enable = gameplay_video_valid;
    assign framebuffer_enable = gameplay_video_valid;
    assign direct_diagnostic_enable = diagnostic_video;
endmodule
