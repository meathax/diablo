// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <array>
#include <cstdint>

namespace diablo::mister::sdl {

// MiSTer digital bits 0..3 are right/left/down/up. Bits 4 onward
// follow the core's J button list: A,B,X,Y,LB,RB,View,Menu,L3,R3,LT,RT.
// Keep this transport contract independent of physical USB controller IDs.
struct GamepadState {
	// SDL controller order: left X/Y, right X/Y, left/right trigger.
	std::array<std::int16_t, 6> axes {};
	// SDL controller order through DPAD_RIGHT (Guide is intentionally unused).
	std::array<bool, 15> buttons {};
};

constexpr std::int16_t ExpandStick(std::uint8_t raw)
{
	const int value = raw < 128 ? raw : static_cast<int>(raw) - 256;
	return static_cast<std::int16_t>(value < 0 ? value * 256 : value * 32767 / 127);
}

constexpr GamepadState DecodeGamepad(std::uint32_t mask, std::uint16_t left,
    std::uint16_t right)
{
	GamepadState state;
	state.axes = { ExpandStick(left & 255), ExpandStick(left >> 8),
		ExpandStick(right & 255), ExpandStick(right >> 8),
		static_cast<std::int16_t>((mask & (1U << 14)) ? 32767 : 0),
		static_cast<std::int16_t>((mask & (1U << 15)) ? 32767 : 0) };
	constexpr std::array<int, 15> bits { 4, 5, 6, 7, 10, -1, 11, 12, 13, 8, 9, 3, 2, 1, 0 };
	for (unsigned i = 0; i < bits.size(); ++i)
		state.buttons[i] = bits[i] >= 0 && (mask & (1U << bits[i])) != 0;
	return state;
}

} // namespace diablo::mister::sdl
