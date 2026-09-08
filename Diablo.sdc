# sys/sys_top.sdc derives the 50.4 MHz core PLL clock and clock uncertainty.
# The template hierarchy is preserved so its clock groups still match.
# CE_PIXEL divides the pixel rate by two; all core registers use clk_sys.

# ADV7513 Rev. B, AC specifications: video setup 1.8 ns, hold 1.3 ns.
# https://www.analog.com/media/en/technical-documentation/data-sheets/adv7513.pdf
# Reserve +/-0.5 ns for board data/clock skew. This is a design budget;
# physical board qualification must verify it, not treat it as a measurement.
# sys_top forwards an inverted clock through hdmiclk_ddr (H=0, L=1).
# Both the normal scaler clock and the direct-video core clock can drive it.
set core_pin [get_pins -compatibility_mode {*emu*pll*PLL_OUTPUT_COUNTER|divclk}]
set hdmi_pin [get_pins -compatibility_mode {pll_hdmi*output_counter|divclk}]
if {[get_collection_size $core_pin] != 1 || [get_collection_size $hdmi_pin] != 1} {
    error "Diablo HDMI constraints require exactly one core and one scaler PLL output"
}
set core_clock [get_clocks {*emu*pll*PLL_OUTPUT_COUNTER|divclk}]
set hdmi_clock [get_clocks {pll_hdmi*output_counter|divclk}]

# C25 HDMI_MCLK forwarded-clock decision: direct, non-inverted forwarding of the sole audio PLL
# output.  This models the forwarded clock only; it adds no I2S data timing.
set c25_audio_mclk_pin [get_pins -compatibility_mode {pll_audio*PLL_OUTPUT_COUNTER|divclk}]
set c25_audio_mclk_src [get_clocks {pll_audio*PLL_OUTPUT_COUNTER|divclk}]
set c25_audio_mclk_out [get_ports {HDMI_MCLK}]
if {[get_collection_size $c25_audio_mclk_pin] != 1 ||
    [get_collection_size $c25_audio_mclk_src] != 1 ||
    [get_collection_size $c25_audio_mclk_out] != 1} {
    error "C25 HDMI_MCLK requires one PLL source pin, source clock, and output port"
}
create_generated_clock -name HDMI_MCLK_FWD \
    -source $c25_audio_mclk_pin \
    -master_clock $c25_audio_mclk_src \
    -divide_by 1 \
    $c25_audio_mclk_out
create_generated_clock -name HDMI_TX_CORE -source $core_pin -master_clock $core_clock -divide_by 1 -invert [get_ports HDMI_TX_CLK]
create_generated_clock -name HDMI_TX_SCALER -source $hdmi_pin -master_clock $hdmi_clock -divide_by 1 -invert -add [get_ports HDMI_TX_CLK]
# The physical clock mux selects one clock at a time. Preserve timing between
# each output clock and its own parent; exclude impossible cross-mux transfers.
set_clock_groups -exclusive -group [get_clocks {*emu*pll*divclk HDMI_TX_CORE}] -group [get_clocks {pll_hdmi*divclk HDMI_TX_SCALER}]
set hdmi_data_ports [get_ports {HDMI_TX_D[*] HDMI_TX_DE HDMI_TX_HS HDMI_TX_VS}]
if {[get_collection_size $hdmi_data_ports] != 27} {error "Missing HDMI video output ports"}
foreach hdmi_clock_name {HDMI_TX_CORE HDMI_TX_SCALER} {
    set_output_delay -clock $hdmi_clock_name -max 2.3 -add_delay $hdmi_data_ports
    set_output_delay -clock $hdmi_clock_name -min -1.8 -add_delay $hdmi_data_ports
}

# C25 core-specific asynchronous/status exceptions.  These collections are
# deliberately exact: a changed top-level interface must fail the STA trial
# instead of silently broadening an exception.
proc c25_exact_ports {label names expected} {
    set ports [get_ports $names]
    set actual [get_collection_size $ports]
    if {$actual != $expected} {
        error "C25 $label expected $expected ports, resolved $actual: $names"
    }
    return $ports
}

# Diablo drives only these LED vector bits as status indicators; the imported
# LED_* pattern does not cover vector members LED[0], LED[2], and LED[6].
set c25_led_outputs [c25_exact_ports "LED status vector" {LED[0] LED[2] LED[6]} 3]
set_false_path -to $c25_led_outputs

# SDCD_SPDIF is card-detect when the SD path is selected and an open-drain,
# self-clocked S/PDIF waveform otherwise.  It has no fabric source clock.
set c25_sdcd [c25_exact_ports "SDCD_SPDIF mode-multiplexed pin" {SDCD_SPDIF} 1]
set_false_path -from $c25_sdcd
set_false_path -to $c25_sdcd

# In this core Diablo.sv drives SD_SCK/SD_MOSI/SD_CS to Z.  sys_top therefore
# uses these board pins as analog-video/Z aliases in the active Diablo modes.
set c25_analog_outputs [c25_exact_ports "Diablo analog aliases" {
    SDIO_CLK SDIO_CMD SDIO_DAT[0] SDIO_DAT[1] SDIO_DAT[2] SDIO_DAT[3] SD_SPI_CS
} 7]
set_false_path -to $c25_analog_outputs
