// MiSTer target entry point. The engine stays upstream-compatible; this
// wrapper selects and admits the transport before DiabloMain starts SDL.
#include "diablo.h"
#include "mister_transport_config.hpp"
#include "mister_transport_sdl.hpp"

#include <cstdio>
#include <cstdlib>

int main(int argc, char **argv)
{
	const auto request = ::diablo::mister::transport::ParseTransportRequest(
		std::getenv("DIABLO_MISTER_TRANSPORT"));
	if (request == ::diablo::mister::transport::TransportRequest::Invalid) {
		std::fprintf(stderr, "Diablo MiSTer wrapper: %s\n",
		             ::diablo::mister::transport::TransportRequestError(request));
		return EXIT_FAILURE;
	}
	if (request == ::diablo::mister::transport::TransportRequest::Enabled
	    && std::getenv("SDL_VIDEODRIVER") == nullptr) {
		// The SDL window is retained for engine surface creation, while the
		// indexed pixels are published to the FPGA transport at presentation.
		if (::setenv("SDL_VIDEODRIVER", "dummy", 0) != 0) {
			std::fputs("Diablo MiSTer wrapper: unable to select SDL dummy video\n", stderr);
			return EXIT_FAILURE;
		}
	}
	if (request == ::diablo::mister::transport::TransportRequest::Enabled
	    && !::diablo::mister::sdl::Initialize()) {
		std::fputs("Diablo MiSTer wrapper: requested transport was not admitted\n", stderr);
		return EXIT_FAILURE;
	}
	const int result = devilution::DiabloMain(argc, argv);
	// Normal engine cleanup is expected to do this first. Keep early engine
	// exits from leaking a mapping acquired before DiabloMain initialized dx.
	if (::diablo::mister::sdl::Active())
		::diablo::mister::sdl::Shutdown();
	return result;
}
