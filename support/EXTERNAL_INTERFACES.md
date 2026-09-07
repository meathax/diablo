# External interface review

The delay12 build constrains HDMI video, with positive setup/hold in all four
reported corners. Its remaining unconstrained ports are inventoried in
`.mister/evidence/native-hdmi-delay12-build.json`. No broad false paths were added.

| Ports | Source behavior | Remaining evidence |
| --- | --- | --- |
| HDMI_I2S, HDMI_LRCLK, HDMI_SCLK | `audio_out.sv` supplies serializer enables; `i2s.v` serializes stereo 16-bit samples at 48/96 kHz | Post-fit clock/data timing and physical audio validation |
| HDMI_MCLK | Direct audio PLL output | Forwarded-clock definition and receiver configuration review |
| HDMI_I2C_SCL/SDA | HDMI configuration bus | SCL/SDA waveform, receiver setup/hold, open-drain rise-time budget |
| HDMI_TX_INT | Asynchronous HDMI status supplied to HPS GP input | HPS sampling/CDC contract |
| IO_SCL/SDA | Board expander bus | Controller waveform, board pull-ups and input sampling |
| SDCD_SPDIF | Card detect input / open-drain SPDIF output | Each supported switch/multiplexer mode and external electrical behavior |
| LED[0,2,6] | Multiplexed board outputs | Trace each selected function before considering a timing exception |
| SDIO_CLK/CMD/DAT, SD_SPI_CS | Multiplexed storage interface | Both input/output modes and board-level timing |
| USER_IO[2,4,5] | User outputs or open-drain I2S | Selected-device timing and open-drain rise time |

The ADV7513 specifies 2 ns setup and hold for I2S data and LRCLK, and SCLK duty
cycle limits. See the [Rev. B datasheet, page 4](https://www.analog.com/media/en/technical-documentation/data-sheets/adv7513.pdf).
The same provisional 0.5 ns skew budget used for video gives a 2.5 ns digital
setup/hold target here; physical verification must establish the board budget.

The Diablo core now drives the standard MiSTer `AUDIO_L` and `AUDIO_R` ports as
signed 16-bit, 48 kHz PCM from its bounded shared-DDR consumer. `AUDIO_MIX` is
disabled, so this is the core's own stereo stream; platform audio serialization
and HDMI routing remain in the imported system logic. The pending board check
must prove queue consumption together with the active framebuffer, then verify
audible left/right channel order and absence of underruns. It must not treat a
successful FPGA queue acknowledgement as physical-audio sign-off.

`support/tests/i2s_interface_tb.sv` checks the unchanged imported serializer with
the two enable intervals used by `audio_out.sv`: eight and four audio-clock cycles.
It reconstructs stereo words at rising SCLK, checks the one-bit LRCLK offset,
channel order, word length, high/low clock duration, and digital setup/hold. It
also resets between modes. The initial pipeline words are deliberately excluded
from payload checks because the serializer loads channel registers on a boundary.

```powershell
iverilog -g2012 -s i2s_interface_tb -o .work/build/i2s-interface-test/test.vvp sys/i2s.v support/tests/i2s_interface_tb.sv
vvp .work/build/i2s-interface-test/test.vvp
```

This is serializer RTL evidence only. It does not simulate the complete mixer,
prove fitted pin delays, establish live sample-rate switching behavior, or qualify
sound on the board. Clock enables and the serializer's delayed SCLK register must
be reflected in any generated-clock/edge constraints; assigning an arbitrary
unrelated ideal clock would not prove the real interface.

The delay12 fitted netlist has now been checked at all four available operating
corners for the three serializer register-to-output paths. Diagnostic reports in
`.mister/evidence/i2s-fitted-path-diagnostic.json` include clock-source propagation
and output routing. Across corners, arrival times range from 6.774 to 20.822 ns.
The temporary 40 ns maximum / 0 ns minimum bounds used to extract those paths
are not production receiver constraints and do not modify `Diablo.sdc`.

In steady 96 kHz mode, data and LRCLK change five master-clock periods before
the sampling SCLK rise; the next change is three periods after it. Subtracting
the full cross-corner arrival spread and the provisional 2.5 ns receiver/skew
allowance leaves over 186 ns setup and 105 ns hold. These conservative derived
bounds exclude additional jitter and mode/reset transients. The 48 kHz spacing
is larger. The next timing action is to encode the verified edge relationship
and validate receiver constraints, including their clock uncertainty, rather
than treating the diagnostic max/min bounds as completed interface sign-off.
