// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "mister_transport_config.hpp"
#include <SDL.h>
#include <cstdlib>
#include <cstring>

namespace diablo::mister::sdl {
inline constexpr const char *TransportControllerName = "MiSTer Diablo Xbox-layout controller";

inline bool AdmitController(int index)
{
	if (transport::ParseTransportRequest(std::getenv("DIABLO_MISTER_TRANSPORT"))
	    != transport::TransportRequest::Enabled) return true;
	const char *name = SDL_JoystickNameForIndex(index);
	return SDL_JoystickIsVirtual(index) && name != nullptr
	    && std::strcmp(name, TransportControllerName) == 0;
}
} // namespace diablo::mister::sdl
