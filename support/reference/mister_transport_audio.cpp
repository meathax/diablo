#include "mister_transport_audio.hpp"

#include "mister_transport_sdl.hpp"

namespace diablo::mister::sdl {

bool ServicePcmAudio(PcmMixCallback mix, void *userdata, std::uint8_t *bytes, int byte_count)
{
	if (!Requested()) return false;
	(void)Adapter::Instance().ServicePcmAudio(mix, userdata, bytes, byte_count);
	return true;
}

} // namespace diablo::mister::sdl
