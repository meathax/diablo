#pragma once

#include <cstddef>
#include <cstdint>

namespace diablo::mister::sdl {

using PcmMixCallback = void (*)(void *, std::uint8_t *, int);

// Returns false for ordinary SDL playback. In transport mode the FPGA queue,
// not the dummy device's sleep interval, determines how much audio to mix.
// A wakeup may mix zero or several chunks, with bounded work and no waiting.
bool ServicePcmAudio(PcmMixCallback mix, void *userdata, std::uint8_t *bytes, int byte_count);

} // namespace diablo::mister::sdl
