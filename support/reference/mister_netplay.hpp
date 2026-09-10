// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <string>

namespace devilution::mister_netplay {

enum class Mode : std::uint8_t {
	None,
	Host,
	Join,
};

struct Request {
	Mode mode = Mode::None;
	std::string code;
	std::uint32_t provider = 0; // DevilutionX SELCONN_ZT
};

// Read the launcher-provided request once at the multiplayer boundary. The
// launcher validates the same file before exporting these environment values;
// the engine still validates the code again before using it as a game name.
Request read_request();

} // namespace devilution::mister_netplay
