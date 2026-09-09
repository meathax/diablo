// SPDX-License-Identifier: GPL-2.0-or-later
#include "mister_gamepad_state.hpp"

using namespace diablo::mister::sdl;

static_assert(ExpandStick(0) == 0);
static_assert(ExpandStick(127) == 32767);
static_assert(ExpandStick(128) == -32768);
static_assert(ExpandStick(255) == -256);
constexpr auto leftOnly = DecodeGamepad(0, 0x807f, 0);
static_assert(leftOnly.axes[0] == 32767 && leftOnly.axes[1] == -32768);
static_assert(leftOnly.axes[2] == 0 && leftOnly.axes[3] == 0);
constexpr auto rightOnly = DecodeGamepad(0, 0, 0x7f80);
static_assert(rightOnly.axes[0] == 0 && rightOnly.axes[1] == 0);
static_assert(rightOnly.axes[2] == -32768 && rightOnly.axes[3] == 32767);
constexpr bool EveryButtonIsIndependent()
{
	constexpr int map[] { 4, 5, 6, 7, 10, -1, 11, 12, 13, 8, 9, 3, 2, 1, 0 };
	for (unsigned bit = 0; bit < 16; ++bit) {
		const auto state = DecodeGamepad(1U << bit, 0, 0);
		for (unsigned b = 0; b < 15; ++b)
			if (state.buttons[b] != (map[b] == static_cast<int>(bit))) return false;
		for (unsigned axis = 0; axis < 4; ++axis)
			if (state.axes[axis] != 0) return false;
		if (state.axes[4] != (bit == 14 ? 32767 : 0)) return false;
		if (state.axes[5] != (bit == 15 ? 32767 : 0)) return false;
	}
	return true;
}
static_assert(EveryButtonIsIndependent());
int main() {}
