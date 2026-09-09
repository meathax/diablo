// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "mister_gamepad_state.hpp"
#include "mister_controller_admission.hpp"
#include <SDL.h>

namespace diablo::mister::sdl {

// Main-thread only. SDL owns event generation and game-controller state, so
// consumers polling buttons see the same state as consumers reading events.
class VirtualGamepad {
public:
	bool Publish(const GamepadState &state)
	{
		if (!Open()) return false;
		for (int axis = 0; axis < 6; ++axis) {
			const Sint16 value = axis < 4 ? state.axes[axis]
			    : (state.axes[axis] == 0 ? -32768 : 32767);
			if (SDL_JoystickSetVirtualAxis(joystick_, axis, value) < 0) return false;
		}
		for (int button = 0; button < 15; ++button)
			if (SDL_JoystickSetVirtualButton(joystick_, button, state.buttons[button]) < 0) return false;
		SDL_JoystickUpdate();
		return true;
	}

	void Close()
	{
		if (joystick_ == nullptr) return;
		const auto instance = SDL_JoystickInstanceID(joystick_);
		SDL_JoystickClose(joystick_);
		joystick_ = nullptr;
		// Device indices can change when unrelated physical devices disappear.
		for (int index = 0; index < SDL_NumJoysticks(); ++index) {
			if (SDL_JoystickGetDeviceInstanceID(index) != instance) continue;
			SDL_JoystickDetachVirtual(index);
			break;
		}
	}

private:
	bool Open()
	{
		if (joystick_ != nullptr) return true;
		// Early transport admission precedes SDL startup. Retry after startup.
		if ((SDL_WasInit(SDL_INIT_GAMECONTROLLER) & SDL_INIT_GAMECONTROLLER) == 0) return false;
		SDL_VirtualJoystickDesc desc {};
		desc.version = SDL_VIRTUAL_JOYSTICK_DESC_VERSION;
		desc.type = SDL_JOYSTICK_TYPE_GAMECONTROLLER;
		desc.naxes = 6;
		desc.nbuttons = 15;
		desc.axis_mask = 0x3f;
		// SDL packs descriptor buttons in mask order. Retain the unused Guide
		// slot or every subsequent button is shifted by one.
		desc.button_mask = 0x7fff;
		desc.name = TransportControllerName;
		const int index = SDL_JoystickAttachVirtualEx(&desc);
		if (index < 0) return false;
		joystick_ = SDL_JoystickOpen(index);
		if (joystick_ == nullptr) SDL_JoystickDetachVirtual(index);
		return joystick_ != nullptr;
	}
	SDL_Joystick *joystick_ = nullptr;
};

} // namespace diablo::mister::sdl
