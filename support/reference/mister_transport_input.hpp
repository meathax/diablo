// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "transport_abi.hpp"
#include "mister_virtual_gamepad.hpp"
#include <SDL.h>
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <optional>

namespace diablo::mister::sdl {

// Main-thread owner of desired/delivered SDL input state. Transport polling and
// runtime lifetime stay in Adapter; this component never maps or owns DDR.
class InputReconciler {
#ifdef DIABLO_MISTER_INPUT_TEST
 friend class InputAdapterTest;
#endif
private:

	static SDL_Scancode Ps2Scancode(std::uint32_t code)
	{
		const bool extended = (code & 0x100U) != 0;
		const std::uint8_t scan = static_cast<std::uint8_t>(code & 0xffU);
		if (extended) {
			switch (scan) {
			case 0x11: return SDL_SCANCODE_RALT;
			case 0x14: return SDL_SCANCODE_RCTRL;
			case 0x4a: return SDL_SCANCODE_KP_DIVIDE;
			case 0x5a: return SDL_SCANCODE_KP_ENTER;
			case 0x69: return SDL_SCANCODE_END;
			case 0x6b: return SDL_SCANCODE_LEFT;
			case 0x6c: return SDL_SCANCODE_HOME;
			case 0x70: return SDL_SCANCODE_INSERT;
			case 0x71: return SDL_SCANCODE_DELETE;
			case 0x72: return SDL_SCANCODE_DOWN;
			case 0x74: return SDL_SCANCODE_RIGHT;
			case 0x75: return SDL_SCANCODE_UP;
			case 0x7a: return SDL_SCANCODE_PAGEDOWN;
			case 0x7d: return SDL_SCANCODE_PAGEUP;
			default: return SDL_SCANCODE_UNKNOWN;
			}
		}
		switch (scan) {
		case 0x05: return SDL_SCANCODE_F1;
		case 0x06: return SDL_SCANCODE_F2;
		case 0x04: return SDL_SCANCODE_F3;
		case 0x0c: return SDL_SCANCODE_F4;
		case 0x03: return SDL_SCANCODE_F5;
		case 0x0b: return SDL_SCANCODE_F6;
		case 0x83: return SDL_SCANCODE_F7;
		case 0x0a: return SDL_SCANCODE_F8;
		case 0x01: return SDL_SCANCODE_F9;
		case 0x09: return SDL_SCANCODE_F10;
		case 0x78: return SDL_SCANCODE_F11;
		case 0x07: return SDL_SCANCODE_F12;
		case 0x76: return SDL_SCANCODE_ESCAPE;
		case 0x0d: return SDL_SCANCODE_TAB;
		case 0x58: return SDL_SCANCODE_CAPSLOCK;
		case 0x12: return SDL_SCANCODE_LSHIFT;
		case 0x59: return SDL_SCANCODE_RSHIFT;
		case 0x14: return SDL_SCANCODE_LCTRL;
		case 0x11: return SDL_SCANCODE_LALT;
		case 0x66: return SDL_SCANCODE_BACKSPACE;
		case 0x5a: return SDL_SCANCODE_RETURN;
		case 0x29: return SDL_SCANCODE_SPACE;
		case 0x45: return SDL_SCANCODE_0;
		case 0x16: return SDL_SCANCODE_1;
		case 0x1e: return SDL_SCANCODE_2;
		case 0x26: return SDL_SCANCODE_3;
		case 0x25: return SDL_SCANCODE_4;
		case 0x2e: return SDL_SCANCODE_5;
		case 0x36: return SDL_SCANCODE_6;
		case 0x3d: return SDL_SCANCODE_7;
		case 0x3e: return SDL_SCANCODE_8;
		case 0x46: return SDL_SCANCODE_9;
		case 0x1c: return SDL_SCANCODE_A;
		case 0x32: return SDL_SCANCODE_B;
		case 0x21: return SDL_SCANCODE_C;
		case 0x23: return SDL_SCANCODE_D;
		case 0x24: return SDL_SCANCODE_E;
		case 0x2b: return SDL_SCANCODE_F;
		case 0x34: return SDL_SCANCODE_G;
		case 0x33: return SDL_SCANCODE_H;
		case 0x43: return SDL_SCANCODE_I;
		case 0x3b: return SDL_SCANCODE_J;
		case 0x42: return SDL_SCANCODE_K;
		case 0x4b: return SDL_SCANCODE_L;
		case 0x3a: return SDL_SCANCODE_M;
		case 0x31: return SDL_SCANCODE_N;
		case 0x44: return SDL_SCANCODE_O;
		case 0x4d: return SDL_SCANCODE_P;
		case 0x15: return SDL_SCANCODE_Q;
		case 0x2d: return SDL_SCANCODE_R;
		case 0x1b: return SDL_SCANCODE_S;
		case 0x2c: return SDL_SCANCODE_T;
		case 0x3c: return SDL_SCANCODE_U;
		case 0x2a: return SDL_SCANCODE_V;
		case 0x1d: return SDL_SCANCODE_W;
		case 0x22: return SDL_SCANCODE_X;
		case 0x35: return SDL_SCANCODE_Y;
		case 0x1a: return SDL_SCANCODE_Z;
		case 0x0e: return SDL_SCANCODE_GRAVE;
		case 0x4e: return SDL_SCANCODE_MINUS;
		case 0x55: return SDL_SCANCODE_EQUALS;
		case 0x54: return SDL_SCANCODE_LEFTBRACKET;
		case 0x5b: return SDL_SCANCODE_RIGHTBRACKET;
		case 0x5d: return SDL_SCANCODE_BACKSLASH;
		case 0x4c: return SDL_SCANCODE_SEMICOLON;
		case 0x52: return SDL_SCANCODE_APOSTROPHE;
		case 0x41: return SDL_SCANCODE_COMMA;
		case 0x49: return SDL_SCANCODE_PERIOD;
		case 0x4a: return SDL_SCANCODE_SLASH;
		default: return SDL_SCANCODE_UNKNOWN;
		}
	}

	// SDL_PushEvent returns 1 for a queued event, 0 when an event filter drops
	// it, and -1 when the queue cannot accept it. A filtered/failed event has not
	// reached the game, so it must not advance delivered input state.
	enum class EventPushResult : std::uint8_t { Queued, Filtered, Failed };

	[[nodiscard]] EventPushResult PushEvent(SDL_Event event)
	{
		const int result = SDL_PushEvent(&event);
		if (result > 0) return EventPushResult::Queued;
		if (result == 0) {
			if ((++input_push_filtered_ & 63U) == 1U)
				std::fputs("Diablo MiSTer transport SDL input event filtered\n", stderr);
			return EventPushResult::Filtered;
		}
		if ((++input_push_drops_ & 63U) == 1U)
			std::fputs("Diablo MiSTer transport SDL input queue full\n", stderr);
		return EventPushResult::Failed;
	}

	[[nodiscard]] static std::optional<std::size_t> KeyIndex(SDL_Scancode scancode)
	{
		const int value = static_cast<int>(scancode);
		if (scancode == SDL_SCANCODE_UNKNOWN || value < 0 || value >= SDL_NUM_SCANCODES)
			return std::nullopt;
		return static_cast<std::size_t>(value);
	}

	[[nodiscard]] static std::uint32_t MouseButtonMask(std::uint32_t ps2_buttons)
	{
		std::uint32_t mask = 0;
		if ((ps2_buttons & 0x1U) != 0) mask |= SDL_BUTTON_LMASK;
		if ((ps2_buttons & 0x2U) != 0) mask |= SDL_BUTTON_RMASK;
		if ((ps2_buttons & 0x4U) != 0) mask |= SDL_BUTTON_MMASK;
		return mask;
	}


	[[nodiscard]] bool KeyWanted(SDL_Scancode scancode) const
	{
		if (!requested_focus_) return false;
		const auto index = KeyIndex(scancode);
		if (!index.has_value()) return false;
		return keyboard_desired_[*index] && !keyboard_repress_[*index];
	}

	[[nodiscard]] bool PhysicalKeyWanted(SDL_Scancode scancode) const
	{
		if (!requested_focus_) return false;
		const auto index = KeyIndex(scancode);
		return index.has_value() && keyboard_desired_[*index] && !keyboard_repress_[*index];
	}

	[[nodiscard]] SDL_Keymod ModifierMask() const
	{
		SDL_Keymod modifiers = KMOD_NONE;
		if (PhysicalKeyWanted(SDL_SCANCODE_LSHIFT)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_LSHIFT);
		if (PhysicalKeyWanted(SDL_SCANCODE_RSHIFT)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_RSHIFT);
		if (PhysicalKeyWanted(SDL_SCANCODE_LCTRL)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_LCTRL);
		if (PhysicalKeyWanted(SDL_SCANCODE_RCTRL)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_RCTRL);
		if (PhysicalKeyWanted(SDL_SCANCODE_LALT)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_LALT);
		if (PhysicalKeyWanted(SDL_SCANCODE_RALT)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_RALT);
		if (caps_lock_) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_CAPS);
		return modifiers;
	}

	[[nodiscard]] EventPushResult PushKey(SDL_Scancode scancode, bool pressed)
	{
		SDL_Event event {};
		event.type = pressed ? SDL_KEYDOWN : SDL_KEYUP;
		event.key.state = pressed ? SDL_PRESSED : SDL_RELEASED;
		event.key.repeat = 0;
		event.key.keysym.scancode = scancode;
		event.key.keysym.sym = SDL_GetKeyFromScancode(scancode);
		event.key.keysym.mod = ModifierMask();
		return PushEvent(event);
	}

	[[nodiscard]] static std::optional<char> TextCharacter(SDL_Scancode scancode, SDL_Keymod modifiers)
	{
		if ((modifiers & (KMOD_CTRL | KMOD_ALT | KMOD_GUI)) != 0) return std::nullopt;
		const bool shifted = (modifiers & KMOD_SHIFT) != 0;
		const bool uppercase = shifted != ((modifiers & KMOD_CAPS) != 0);
		if (scancode >= SDL_SCANCODE_A && scancode <= SDL_SCANCODE_Z) {
			const char base = static_cast<char>('a' + (static_cast<int>(scancode) - static_cast<int>(SDL_SCANCODE_A)));
			return uppercase ? static_cast<char>(base - 'a' + 'A') : base;
		}
		static constexpr std::array<char, 10> digits = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'};
		static constexpr std::array<char, 10> shifted_digits = {')', '!', '@', '#', '$', '%', '^', '&', '*', '('};
		if (scancode >= SDL_SCANCODE_0 && scancode <= SDL_SCANCODE_9) {
			const auto index = static_cast<std::size_t>(static_cast<int>(scancode) - static_cast<int>(SDL_SCANCODE_0));
			return shifted ? shifted_digits[index] : digits[index];
		}
		switch (scancode) {
		case SDL_SCANCODE_SPACE: return ' ';
		case SDL_SCANCODE_MINUS: return shifted ? '_' : '-';
		case SDL_SCANCODE_EQUALS: return shifted ? '+' : '=';
		case SDL_SCANCODE_LEFTBRACKET: return shifted ? '{' : '[';
		case SDL_SCANCODE_RIGHTBRACKET: return shifted ? '}' : ']';
		case SDL_SCANCODE_BACKSLASH: return shifted ? '|' : '\\';
		case SDL_SCANCODE_SEMICOLON: return shifted ? ':' : ';';
		case SDL_SCANCODE_APOSTROPHE: return shifted ? '"' : '\'';
		case SDL_SCANCODE_GRAVE: return shifted ? '~' : '`';
		case SDL_SCANCODE_COMMA: return shifted ? '<' : ',';
		case SDL_SCANCODE_PERIOD: return shifted ? '>' : '.';
		case SDL_SCANCODE_SLASH: return shifted ? '?' : '/';
		default: return std::nullopt;
		}
	}

	[[nodiscard]] bool PushText(SDL_Scancode scancode)
	{
		// A text event is only meaningful while the gameplay window owns focus
		// and SDL text input is active. Treat an inactive/non-character key as
		// consumed so it does not remain pending forever; retain a failed or
		// filtered event for the next bounded reconciliation pass.
		if (!requested_focus_ || !delivered_focus_ || SDL_IsTextInputActive() != SDL_TRUE) return true;
		const auto character = TextCharacter(scancode, ModifierMask());
		if (!character.has_value()) return true;
		SDL_Event event {};
		event.type = SDL_TEXTINPUT;
		event.text.text[0] = *character;
		event.text.text[1] = '\0';
		return PushEvent(event) == EventPushResult::Queued;
	}

	[[nodiscard]] bool AnyDeliveredInput() const
	{
		return std::any_of(keyboard_delivered_.begin(), keyboard_delivered_.end(), [](bool value) { return value; })
		    || mouse_delivered_buttons_ != 0;
	}

public:
	void ReconcileInputState()
	{
		constexpr std::size_t kMaximumReconciledEvents = 32;
		std::size_t budget = kMaximumReconciledEvents;
		if (requested_focus_ != delivered_focus_ && budget != 0) {
			SDL_Event event {};
			event.type = SDL_WINDOWEVENT;
			event.window.event = requested_focus_ ? SDL_WINDOWEVENT_FOCUS_GAINED : SDL_WINDOWEVENT_FOCUS_LOST;
			if (PushEvent(event) == EventPushResult::Queued)
				delivered_focus_ = requested_focus_;
			--budget;
		}

		const bool deliver_gameplay = requested_focus_ && delivered_focus_;
		// SDL_PushEvent does not update SDL's polled keyboard modifiers.
		// Mouse actions and text/menu handlers query SDL_GetModState directly.
		SDL_SetModState(deliver_gameplay ? ModifierMask() : KMOD_NONE);
		(void)gamepad_.Publish(deliver_gameplay
		    ? DecodeGamepad(joystick_desired_mask_ & ~joystick_repress_mask_,
		          joystick_left_, joystick_right_)
		    : GamepadState {});
		for (std::size_t index = 0; index < keyboard_delivered_.size() && budget != 0; ++index) {
			const auto scancode = static_cast<SDL_Scancode>(index);
			const bool target = deliver_gameplay && KeyWanted(scancode);
			if (keyboard_delivered_[index] == target) continue;
			if (PushKey(scancode, target) != EventPushResult::Queued) break;
			keyboard_delivered_[index] = target;
			--budget;
		}

		// Text input is a second SDL event and can be filtered or rejected even
		// after its keydown was accepted. Keep one pending bit per physical key
		// so a later reconciliation can deliver it without duplicating text.
		for (std::size_t index = 0; index < text_pending_.size() && budget != 0; ++index) {
			if (!text_pending_[index]) continue;
			const auto scancode = static_cast<SDL_Scancode>(index);
			if (!keyboard_desired_[index]) {
				text_pending_[index] = false;
				continue;
			}
			if (!keyboard_delivered_[index] || !deliver_gameplay) continue;
			if (!PushText(scancode)) break;
			text_pending_[index] = false;
			--budget;
		}

		static constexpr std::array<std::uint8_t, 3> mouse_buttons = {
			SDL_BUTTON_LEFT, SDL_BUTTON_RIGHT, SDL_BUTTON_MIDDLE,
		};
		const std::uint32_t mouse_target = deliver_gameplay
		    ? (mouse_desired_buttons_ & ~mouse_repress_mask_) : 0;
		for (std::size_t index = 0; index < mouse_buttons.size() && budget != 0; ++index) {
			const std::uint32_t bit = 1U << index;
			if ((mouse_delivered_buttons_ & bit) == (mouse_target & bit)) continue;
			SDL_Event event {};
			const bool pressed = (mouse_target & bit) != 0;
			event.type = pressed ? SDL_MOUSEBUTTONDOWN : SDL_MOUSEBUTTONUP;
			event.button.button = mouse_buttons[index];
			event.button.state = pressed ? SDL_PRESSED : SDL_RELEASED;
			event.button.clicks = 1;
			event.button.x = mouse_x_;
			event.button.y = mouse_y_;
			if (PushEvent(event) != EventPushResult::Queued) break;
			if (pressed) mouse_delivered_buttons_ |= bit;
			else mouse_delivered_buttons_ &= ~bit;
			--budget;
		}

		if (overflow_refocus_pending_ && !requested_focus_ && !delivered_focus_ && !AnyDeliveredInput()) {
			overflow_refocus_pending_ = false;
			requested_focus_ = true;
			if (budget != 0) {
				SDL_Event event {};
				event.type = SDL_WINDOWEVENT;
				event.window.event = SDL_WINDOWEVENT_FOCUS_GAINED;
				if (PushEvent(event) == EventPushResult::Queued)
					delivered_focus_ = true;
			}
		}
	}
private:

public:
	void PushKeyboard(const transport::InputEvent &input)
	{
		const SDL_Scancode scancode = Ps2Scancode(input.code);
		const auto index = KeyIndex(scancode);
		if (!index.has_value()) return;
		const bool pressed = input.value0 != 0;
		const bool was_pressed = keyboard_desired_[*index];
		keyboard_desired_[*index] = pressed;
		if (!pressed) {
			keyboard_repress_[*index] = false;
			text_pending_[*index] = false;
		} else if (!was_pressed) {
			// ReconcileInputState decides whether the keydown and its text event
			// actually reached SDL. This remains pending when either is filtered.
			text_pending_[*index] = true;
		}
		if (scancode == SDL_SCANCODE_CAPSLOCK && pressed && !was_pressed) caps_lock_ = !caps_lock_;
		ReconcileInputState();
	}
private:

public:
	void PushMouse(const transport::InputEvent &input)
	{
		const std::uint32_t buttons = (input.code >> 8U) & 0x7U;
		const std::int32_t dx = input.value0;
		const std::int32_t dy = input.value1;
		mouse_desired_buttons_ = buttons;
		mouse_repress_mask_ &= buttons;
		// The PS/2 deltas are untrusted signed 32-bit values. Widen before
		// adding so an extreme packet cannot invoke signed-overflow UB before
		// the cursor is clamped to the framebuffer bounds.
		const auto next_x = static_cast<std::int64_t>(mouse_x_) + static_cast<std::int64_t>(dx);
		const auto next_y = static_cast<std::int64_t>(mouse_y_) + static_cast<std::int64_t>(dy);
		mouse_x_ = static_cast<std::int32_t>(std::clamp<std::int64_t>(
			next_x, 0, static_cast<std::int64_t>(transport::FRAME_WIDTH - 1U)));
		mouse_y_ = static_cast<std::int32_t>(std::clamp<std::int64_t>(
			next_y, 0, static_cast<std::int64_t>(transport::FRAME_HEIGHT - 1U)));
		if (requested_focus_ && delivered_focus_ && (dx != 0 || dy != 0)) {
			SDL_Event motion {};
			motion.type = SDL_MOUSEMOTION;
			motion.motion.which = 0;
			motion.motion.state = MouseButtonMask(mouse_desired_buttons_ & ~mouse_repress_mask_);
			motion.motion.x = mouse_x_;
			motion.motion.y = mouse_y_;
			motion.motion.xrel = dx;
			motion.motion.yrel = dy;
			(void)PushEvent(motion);
		}
		const auto wheel = static_cast<std::int8_t>(input.code & 0xffU);
		if (requested_focus_ && delivered_focus_ && wheel != 0) {
			SDL_Event scroll {};
			scroll.type = SDL_MOUSEWHEEL;
			scroll.wheel.which = 0;
			scroll.wheel.x = 0;
			scroll.wheel.y = wheel;
			scroll.wheel.direction = SDL_MOUSEWHEEL_NORMAL;
			(void)PushEvent(scroll);
		}
		ReconcileInputState();
	}
private:

public:
	void PushJoystick(const transport::InputEvent &input)
	{
		const std::uint32_t buttons = static_cast<std::uint32_t>(input.buttons);
		joystick_left_ = static_cast<std::uint16_t>(input.value0);
		joystick_right_ = static_cast<std::uint16_t>(input.value1);
		joystick_desired_mask_ = buttons & 0xffffU;
		joystick_repress_mask_ &= joystick_desired_mask_;
		ReconcileInputState();
	}
private:

public:
	void PushFocus(bool focused)
	{
		requested_focus_ = focused;
		if (!focused) {
			for (std::size_t index = 0; index < keyboard_desired_.size(); ++index) {
				keyboard_repress_[index] = keyboard_repress_[index] || keyboard_desired_[index];
				text_pending_[index] = false;
			}
			joystick_repress_mask_ |= joystick_desired_mask_;
			mouse_repress_mask_ |= mouse_desired_buttons_;
		}
		ReconcileInputState();
	}
private:

public:
	void RecoverInputAfterDiscontinuity()
	{
		joystick_left_ = joystick_right_ = 0;
		keyboard_desired_.fill(false);
		keyboard_repress_.fill(false);
		joystick_desired_mask_ = 0;
		joystick_repress_mask_ = 0;
		mouse_desired_buttons_ = 0;
		mouse_repress_mask_ = 0;
		requested_focus_ = false;
		overflow_refocus_pending_ = true;
		ReconcileInputState();
	}
private:

public:
	void ResetInputState()
	{
		gamepad_.Close();
		joystick_left_ = joystick_right_ = 0;
		keyboard_desired_.fill(false);
		keyboard_repress_.fill(false);
		text_pending_.fill(false);
		keyboard_delivered_.fill(false);
		joystick_desired_mask_ = 0;
		joystick_repress_mask_ = 0;
		mouse_desired_buttons_ = 0;
		mouse_repress_mask_ = 0;
		mouse_delivered_buttons_ = 0;
		requested_focus_ = true;
		delivered_focus_ = true;
		overflow_refocus_pending_ = false;
		caps_lock_ = false;
		SDL_SetModState(KMOD_NONE);
		input_push_drops_ = 0;
		input_push_filtered_ = 0;
	}
private:

public:
	static bool InputTraceEnabled()
	{
		static const bool enabled = [] {
			const char *value = std::getenv("DIABLO_MISTER_INPUT_TRACE");
			return value != nullptr && (std::strcmp(value, "1") == 0
			                            || std::strcmp(value, "true") == 0);
		}();
		return enabled;
	}
private:

public:
	static void TraceInput(const transport::InputEvent &input)
	{
		if (!InputTraceEnabled()) return;
		std::fprintf(stderr, "Diablo MiSTer input event type=%u code=0x%08x value0=%d value1=%d buttons=0x%016llx\n",
		             input.type, input.code, input.value0, input.value1,
		             static_cast<unsigned long long>(input.buttons));
	}
private:

	std::array<bool, SDL_NUM_SCANCODES> keyboard_desired_ {};
	std::array<bool, SDL_NUM_SCANCODES> keyboard_repress_ {};
	std::array<bool, SDL_NUM_SCANCODES> text_pending_ {};
	std::array<bool, SDL_NUM_SCANCODES> keyboard_delivered_ {};
	std::uint32_t joystick_desired_mask_ = 0;
	std::uint16_t joystick_left_ = 0;
	std::uint16_t joystick_right_ = 0;
	VirtualGamepad gamepad_;
	std::uint32_t joystick_repress_mask_ = 0;
	std::uint32_t mouse_desired_buttons_ = 0;
	std::uint32_t mouse_repress_mask_ = 0;
	std::uint32_t mouse_delivered_buttons_ = 0;
	bool requested_focus_ = true;
	bool delivered_focus_ = true;
	bool overflow_refocus_pending_ = false;
	bool caps_lock_ = false;
	std::int32_t mouse_x_ = transport::FRAME_WIDTH / 2;
	std::int32_t mouse_y_ = transport::FRAME_HEIGHT / 2;
	std::uint32_t input_push_drops_ = 0;
	std::uint32_t input_push_filtered_ = 0;
};

} // namespace diablo::mister::sdl
