#pragma once

#include <cstddef>
#include <cstdint>

namespace diablo::mister::sdl {

// Called by the transport overlay's Aulib SDL callback. The callback owns the
// buffer only for the duration of the call; the adapter copies complete S16
// stereo frames into the bounded FPGA PCM ring without waiting.
void PublishPcmBytes(const std::uint8_t *bytes, std::size_t byte_count);

} // namespace diablo::mister::sdl
