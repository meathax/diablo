#pragma once

#include "transport_abi.hpp"

#include <array>
#include <cstdint>
#include <expected>
#include <span>

namespace diablo::mister::transport {

struct InputState {
	InputSnapshot snapshot {};
	std::array<std::uint64_t, 8> keyboard {};
	std::uint32_t next_sequence = 0;
	std::uint64_t observed_dropped = 0;
	std::int32_t left_analog = 0;
	std::int32_t right_analog = 0;
	std::uint32_t mouse_buttons = 0;
	std::int32_t mouse_wheel = 0;
};

// Converts the bounded FPGA event ring into state that the engine can sample at
// its normal tick boundary. Overflow is recovered before the caller resumes
// consuming deltas, which prevents a dropped key-up or motion edge from
// leaving stale state active forever.
class InputConsumer {
public:
	InputConsumer(AbiView view, std::uint32_t epoch)
		: view_(view)
		, epoch_(epoch)
	{
	}

	[[nodiscard]] const InputState &state() const { return state_; }

	[[nodiscard]] std::expected<std::size_t, AttachError> Poll(std::span<InputEvent> scratch)
	{
		auto dropped = view_.ArmInputDropped(epoch_);
		if (!dropped.has_value()) return std::unexpected(dropped.error());
		if (*dropped != state_.observed_dropped) {
			state_.observed_dropped = *dropped;
			ResetAfterOverflow();
			if (!view_.ArmRecoverInput(epoch_, state_.snapshot))
				return std::unexpected(AttachError::BadLayout);
			return std::unexpected(AttachError::InputOverflow);
		}

		auto consumed = view_.ArmConsumeInput(scratch, epoch_);
		if (!consumed.has_value()) {
			if (consumed.error() != AttachError::InputOverflow) return consumed;
			ResetAfterOverflow();
			if (!view_.ArmRecoverInput(epoch_, state_.snapshot))
				return std::unexpected(AttachError::BadLayout);
			return std::unexpected(AttachError::InputOverflow);
		}
		for (const InputEvent &event : scratch.first(*consumed)) Apply(event);
		return consumed;
	}

	// Returns the state for one engine tick and starts a fresh motion/wheel
	// accumulation window without changing held buttons or keyboard state.
	[[nodiscard]] InputSnapshot TakeSnapshot()
	{
		const InputSnapshot result = state_.snapshot;
		state_.snapshot.mouse_dx = 0;
		state_.snapshot.mouse_dy = 0;
		state_.mouse_wheel = 0;
		return result;
	}

private:
	void ResetAfterOverflow()
	{
		state_.keyboard.fill(0);
		state_.snapshot.mouse_dx = 0;
		state_.snapshot.mouse_dy = 0;
		state_.mouse_buttons = 0;
		state_.mouse_wheel = 0;
		state_.next_sequence = std::atomic_ref<std::uint32_t>(
			view_.header().input.producer_sequence).load(std::memory_order_acquire);
	}

	void Apply(const InputEvent &event)
	{
		state_.next_sequence = event.sequence + 1;
		state_.snapshot.buttons = event.buttons;
		switch (event.type) {
		case INPUT_EVENT_KEYBOARD: {
			const std::uint32_t key = event.code & 0x1ffU;
			const std::size_t word = key >> 6;
			const std::uint64_t mask = std::uint64_t { 1 } << (key & 63U);
			if (event.value0 != 0)
				state_.keyboard[word] |= mask;
			else
				state_.keyboard[word] &= ~mask;
			break;
		}
		case INPUT_EVENT_MOUSE:
			state_.mouse_buttons = (event.code >> 8) & 0x7U;
			state_.mouse_wheel = static_cast<std::int8_t>(event.code & 0xffU);
			state_.snapshot.mouse_x += event.value0;
			state_.snapshot.mouse_y += event.value1;
			state_.snapshot.mouse_dx += event.value0;
			state_.snapshot.mouse_dy += event.value1;
			break;
		case INPUT_EVENT_JOYSTICK:
			state_.left_analog = event.value0;
			state_.right_analog = event.value1;
			break;
		case INPUT_EVENT_FOCUS:
			state_.snapshot.focus_generation++;
			break;
		default:
			break;
		}
	}

	AbiView view_;
	std::uint32_t epoch_;
	InputState state_ {};
};

} // namespace diablo::mister::transport
