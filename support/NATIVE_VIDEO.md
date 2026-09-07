# Native FPGA video bring-up

Step 2 replaces the imported noise demo with `rtl/native_test_pattern.sv`.
The core PLL requests 50.4 MHz; alternating pixel enables produce 25.2 MHz.
Timing is 640 active + 16 front porch + 96 sync + 48 back porch horizontally,
and 480 active + 10 front porch + 2 sync + 33 back porch vertically.
Both sync pulses are negative. The resulting 800×525 timing is 60 Hz progressive.
The Quartus clock report and physical output must still confirm these values.

The OSD selects color bars, one-pixel checks with a center cross, or RGB/grayscale
ramps covering all 256 levels. Each has a one-pixel white border. Mode changes
take effect at the frame boundary. User reset preserves video timing; loss of
PLL lock suppresses pixel enables and active video until lock is synchronized.
The forced-scandoubler setting does not double this already progressive signal.

Video source selection is explicit. The `Video source` OSD option defaults to
`Gameplay`; `Diagnostics` selects the native test-pattern generator and its
`Test pattern` sub-option. In gameplay mode, a valid transport session and an
atomically committed indexed frame assert `VGA_SCALER`, so the MiSTer
framebuffer/scaler consumes the core's `FB_EN`, `FB_BASE`, `FB_FORMAT`, stride
and staged palette rather than the direct RGB diagnostic bus. Before the first
valid frame, after a transport/DDR fault, or during an invalid session, the
direct bus emits a deterministic dark-red startup/error screen. It emits black
for normal gameplay while the framework scaler is selected. This prevents a
colour-bar pattern from silently being treated as a working gameplay mode.
The source policy is implemented in `Diablo.sv` and covered by the native
pattern RTL fixture; it still requires mode-matrix, target and physical
gameplay evidence before output acceptance is closed.

The framework mux in `sys/sys_top.v` remains an external acceptance boundary.
`vga_fb` is `cfg[12] | VGA_SCALER`, `vga_scaler` is `cfg[2] | VGA_SCALER`, and
`vgas_en` selects framework framebuffer/scaler RGB (`vgas_o`) over direct core
RGB (`vga_o`) for analog output. HDMI selects the direct-video path only when
`direct_video` is set and `vga_fb` is clear. `VGA_SCALER` can force the gameplay
path, but there is no inverse core signal that forces direct RGB when a user
configuration bit is already set. Diagnostics therefore must be qualified with
the actual MiSTer `cfg[12]`, `cfg[2]` and `direct_video` settings; the local
pattern test proves core source intent but does not close the framework/physical
mux gate.

Run the RTL regression from the workspace root:

```powershell
iverilog -g2012 -s native_test_pattern_tb -o .work/build/native-pattern-test/pattern.vvp rtl/native_test_pattern.sv support/tests/native_test_pattern_tb.sv
vvp .work/build/native-pattern-test/pattern.vvp
```

The initial fresh Quartus build uses the isolated source snapshot in
`.work/build/fpga-native640/source`; its parent contains the per-file source
hashes and compiler log. No earlier Quartus database is copied into that snapshot.
Run full flow through the installed launcher, then convert the resulting SOF:

```powershell
& D:/vibes/fpga/bin/quartus-safe.ps1 D:/Q17/quartus/bin64/quartus_sh.exe --flow compile Diablo
& D:/vibes/fpga/bin/quartus-safe.ps1 -Executable D:/Q17/quartus/bin64/quartus_cpf.exe -ArgumentList @('-c','-o','bitstream_compression=on','output_files/Diablo.sof','output_files/Diablo.compressed.rbf')
```

Inspect fitted resource/memory reports, actual clocks, setup/hold and unconstrained
paths before selecting an RBF for board testing. Keep the imported `sys/` files
unchanged and investigate core issues before altering framework constraints.

The initial build passed internal timing at the slow 1100 mV, 100 °C corner, but
left HDMI outputs unconstrained. A diagnostic using the ADV7513 receiver's
1.8 ns setup and 1.3 ns hold requirements found only 0.291 ns setup margin
before board skew. `Diablo.sdc` now models both forwarded HDMI clock sources and
reserves 0.5 ns of skew on each side. That is a design budget to verify on the
board, not measured trace data. The template already requests HDMI output-register
placement; all-corner analysis now accompanies these constraints in the snapshot at
`.work/build/fpga-native640-timed/source`. That build completed but failed HDMI
setup: -0.209 ns at slow 100 °C and -0.212 ns at slow -40 °C. Its positive hold
margins do not override that failure. Quartus exit status alone is insufficient.
The next isolated build, `.work/build/fpga-native640-delay12/source`, tests a
12-tap D5 delay assignment on the forwarded clock. The fitter confirms that setting;
all four reported corners pass, with minimum HDMI setup +0.190 ns and hold +0.391 ns.
Its compressed RBF is generated and all 73 snapshot files match the working sources.
See `.mister/evidence/native-hdmi-delay12-build.json` for hashes and margins.
There are still four unconstrained inputs and 22 unconstrained outputs involving
framework I2C, audio and multiplexed IO. Those require interface-specific review;
this result does not establish complete external-interface timing qualification.
The receiver requirements come from the [ADV7513 Rev. B datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/adv7513.pdf).

Hardware acceptance remains open: load the verified RBF on the actual MiSTer,
check all four borders and pixel geometry on HDMI and applicable 31 kHz analog
output, check RGB order/ramp precision, and confirm stable sync through OSD mode
changes and reset. Record the RBF hash, MiSTer configuration, display path and
observed timing. This pattern is not Diablo gameplay or ARM/FPGA performance proof.
