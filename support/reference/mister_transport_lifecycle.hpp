#pragma once

#include "mister_transport_runtime.hpp"

#include <atomic>
#include <cstdint>
#include <expected>
#include <memory>

namespace diablo::mister::sdl {

// Owns the transport runtime and the gates that protect lifecycle transitions
// from an in-flight SDL audio callback. No frame, input or audio payload state
// lives here; those owners are reset by Adapter at the lifecycle boundary.
class TransportLifecycle {
#ifdef DIABLO_MISTER_INPUT_TEST
friend class InputAdapterTest;
#endif
public:
	using RuntimePtr = std::shared_ptr<transport::TransportRuntime>;

	[[nodiscard]] std::expected<void, transport::RuntimeError> Initialize()
	{
		if (Runtime()) return {};
		auto opened = transport::TransportRuntime::Open();
		if (!opened.has_value()) return std::unexpected(opened.error());
		RequestAudioReset();
		runtime_transition_generation_.store(0, std::memory_order_release);
		runtime_.store(std::make_shared<transport::TransportRuntime>(std::move(*opened)),
		               std::memory_order_release);
		startup_waited_ = false;
		return {};
	}

	void Shutdown()
	{
		(void)runtime_.exchange(RuntimePtr {}, std::memory_order_acq_rel);
		startup_waited_ = false;
		RequestAudioReset();
	}

	[[nodiscard]] RuntimePtr Runtime() const
	{
		return runtime_.load(std::memory_order_acquire);
	}

	[[nodiscard]] bool BeginAudioCallback()
	{
		const std::uint32_t generation =
			runtime_transition_generation_.load(std::memory_order_acquire);
		if ((generation & 1U) != 0) return false;
		audio_callbacks_inflight_.fetch_add(1U, std::memory_order_acq_rel);
		if (runtime_transition_generation_.load(std::memory_order_acquire) == generation)
			return true;
		(void)audio_callbacks_inflight_.fetch_sub(1U, std::memory_order_release);
		return false;
	}

	void EndAudioCallback()
	{
		(void)audio_callbacks_inflight_.fetch_sub(1U, std::memory_order_release);
	}

	[[nodiscard]] bool BeginRuntimeTransition()
	{
		std::uint32_t generation =
			runtime_transition_generation_.load(std::memory_order_acquire);
		while ((generation & 1U) == 0) {
			if (runtime_transition_generation_.compare_exchange_weak(
			        generation, generation + 1U, std::memory_order_acq_rel,
			        std::memory_order_acquire)) {
				if (audio_callbacks_inflight_.load(std::memory_order_acquire) == 0)
					return true;
				EndRuntimeTransition();
				return false;
			}
		}
		return false;
	}

	void EndRuntimeTransition()
	{
		(void)runtime_transition_generation_.fetch_add(1U, std::memory_order_release);
	}

	[[nodiscard]] bool WaitForFpgaReady(unsigned timeout_ms)
	{
		if (startup_waited_) return true;
		auto runtime = Runtime();
		if (!runtime) return false;
		startup_waited_ = true;
		return runtime->WaitForFpgaReady(timeout_ms);
	}

	void ResetStartupWait()
	{
		startup_waited_ = false;
	}

	void RequestAudioReset()
	{
		(void)audio_reset_generation_.fetch_add(1U, std::memory_order_release);
	}

	[[nodiscard]] std::uint32_t AudioResetGeneration() const
	{
		return audio_reset_generation_.load(std::memory_order_acquire);
	}

private:
	std::atomic<RuntimePtr> runtime_;
	std::atomic<std::uint32_t> audio_reset_generation_ {1};
	std::atomic<std::uint32_t> audio_callbacks_inflight_ {0};
	std::atomic<std::uint32_t> runtime_transition_generation_ {0};
	bool startup_waited_ = false;
};

} // namespace diablo::mister::sdl
