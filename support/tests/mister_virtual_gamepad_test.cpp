// SPDX-License-Identifier: GPL-2.0-or-later
#define SDL_MAIN_HANDLED
#include "mister_virtual_gamepad.hpp"
#include "mister_transport_input.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>

void Check(bool ok, const char *message)
{
	if (ok) return;
	std::fprintf(stderr, "%s: %s\n", message, SDL_GetError());
	std::exit(1);
}

void SetProcessEnvironment(const char *name, const char *value)
{
#if defined(_WIN32)
	_putenv_s(name, value);
#else
	setenv(name, value, 1);
#endif
}

int FindTransportJoystick()
{
	for (int index = 0; index < SDL_NumJoysticks(); ++index) {
		const char *name = SDL_JoystickNameForIndex(index);
		if (name != nullptr && std::strcmp(name, diablo::mister::sdl::TransportControllerName) == 0)
			return index;
	}
	return -1;
}

int main()
{
	SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
	SDL_setenv("SDL_VIDEODRIVER", "dummy", 1);
	Check(SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER | SDL_INIT_VIDEO) == 0,
	      "SDL initialization");
	auto *window = SDL_CreateWindow("MiSTer transport regression", 0, 0, 640, 480, SDL_WINDOW_HIDDEN);
	Check(window != nullptr, "dummy video window");
	diablo::mister::sdl::VirtualGamepad device;
	Check(device.Publish({}), "register neutral controller");
	const int transport_index = FindTransportJoystick();
	Check(transport_index >= 0, "transport virtual device registered");
	Check(SDL_IsGameController(transport_index), "recognized as game controller");
	SetProcessEnvironment("DIABLO_MISTER_TRANSPORT", "1");
	Check(diablo::mister::sdl::AdmitController(transport_index), "transport controller admitted");
	const int unrelated = SDL_JoystickAttachVirtual(SDL_JOYSTICK_TYPE_GAMECONTROLLER, 6, 15, 0);
	Check(unrelated >= 0, "unrelated device attached");
	Check(!diablo::mister::sdl::AdmitController(unrelated), "unrelated controller rejected in transport");
	SetProcessEnvironment("DIABLO_MISTER_TRANSPORT", "0");
	Check(diablo::mister::sdl::AdmitController(unrelated), "native controller preserved");
	Check(SDL_JoystickDetachVirtual(unrelated) == 0, "unrelated device removed");
	auto *controller = SDL_GameControllerOpen(transport_index);
	Check(controller != nullptr, "open controller");
	Check(device.Publish(diablo::mister::sdl::DecodeGamepad(1U << 4, 0x007f, 0x8000)), "publish inputs");
	SDL_GameControllerUpdate();
	Check(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX) == 32767, "left X");
	Check(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTY) == -32768, "right Y");
	Check(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_RIGHTX) == 0, "right X independent");
	Check(SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A), "A button");
	Check(!SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_DPAD_RIGHT), "stick not dpad");
	Check(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERLEFT) == 0, "released trigger");
	for (unsigned bit = 0; bit < 16; ++bit) {
		const auto expected = diablo::mister::sdl::DecodeGamepad(1U << bit, 0, 0);
		Check(device.Publish(expected), "publish isolated button");
		for (int button = 0; button < 15; ++button) {
			const bool actual = SDL_GameControllerGetButton(controller,
			    static_cast<SDL_GameControllerButton>(button)) != 0;
			if (actual != expected.buttons[button]) {
				std::fprintf(stderr, "transport bit %u, SDL button %d\n", bit, button);
				Check(false, "isolated button mapping");
			}
		}
		Check(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERLEFT) == expected.axes[4], "left trigger mapping");
		Check(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) == expected.axes[5], "right trigger mapping");
	}
	Check(device.Publish({}), "neutral release");
	Check(!SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A), "A released");
	Check(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX) == 0, "axis released");
	SDL_GameControllerClose(controller);
	device.Close();
	Check(FindTransportJoystick() < 0, "transport device removed");
	diablo::mister::sdl::InputReconciler input;
	diablo::mister::transport::InputEvent event {};
	event.buttons = 1U << 4;
	event.value0 = 127;
	input.PushJoystick(event);
	controller = SDL_GameControllerOpen(FindTransportJoystick());
	Check(controller != nullptr, "reconciler controller registered");
	Check(SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A), "reconciler A");
	input.PushFocus(false);
	Check(!SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A), "focus releases A");
	Check(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX) == 0, "focus neutralizes stick");
	input.PushFocus(true);
	Check(!SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A), "focus does not repress held A");
	event.buttons = 0;
	input.PushJoystick(event);
	event.buttons = 1U << 4;
	input.PushJoystick(event);
	Check(SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A), "neutral/repress restores A");
	input.RecoverInputAfterDiscontinuity();
	Check(!SDL_GameControllerGetButton(controller, SDL_CONTROLLER_BUTTON_A), "overflow releases A");
	Check(SDL_GameControllerGetAxis(controller, SDL_CONTROLLER_AXIS_LEFTX) == 0, "overflow neutralizes stick");
	SDL_GameControllerClose(controller);
	input.ResetInputState();
	SDL_DestroyWindow(window);
	SDL_Quit();
}
