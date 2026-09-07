#include "mister_transport_audio.hpp"

#include "mister_transport_sdl.hpp"

namespace diablo::mister::sdl {

void PublishPcmBytes(const std::uint8_t *bytes, std::size_t byte_count)
{
	(void)Adapter::Instance().PublishPcmBytes(bytes, byte_count);
}

} // namespace diablo::mister::sdl
