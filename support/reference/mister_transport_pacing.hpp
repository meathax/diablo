#pragma once

#include <SDL.h>

#include <chrono>
#include <cstdint>
#include <thread>

namespace diablo::mister::sdl {

// Fixed deadlines absorb scheduler oversleep. FPGA retirement feedback takes
// precedence when available, so delivery follows scanout rather than a second clock.
class FramePacer {
public:
	void Pace()
	{
		const auto frequency = SDL_GetPerformanceFrequency();
		PaceWithClock(frequency, [] { return SDL_GetPerformanceCounter(); },
		    [frequency](std::uint64_t ticks) {
			    const auto ns = (ticks * 1000000000ULL + frequency - 1) / frequency;
			    std::this_thread::sleep_for(std::chrono::nanoseconds(ns));
		    });
	}

	// Injectable clock makes cadence, oversleep and hitch tests deterministic.
	template <typename Clock, typename Sleep>
	void PaceWithClock(std::uint64_t frequency, Clock now, Sleep sleep)
	{
		if (frequency == 0)
			return;
		auto current = now();
		const auto period = (frequency + 59) / 60;
		if (initialized_) {
			while (current < deadline_) {
				sleep(deadline_ - current);
				current = now();
			}
		}
		// A whole missed period is a hitch: discard backlog, never burst to catch up.
		deadline_ = !initialized_ || current - deadline_ >= period
		    ? current + period : deadline_ + period;
		initialized_ = true;
		last_ = current;
	}

	template <typename Feedback>
	void PaceWithFeedback(Feedback feedback)
	{
		const auto frequency = SDL_GetPerformanceFrequency();
		PaceWithFeedbackClock(frequency, [] { return SDL_GetPerformanceCounter(); },
		    [frequency](std::uint64_t ticks) {
			    std::this_thread::sleep_for(std::chrono::nanoseconds(
			        (ticks * 1000000000ULL + frequency - 1) / frequency));
		    }, feedback);
	}

	// Feedback is the FPGA's retirement sequence, not an assumed display rate.
	// A stalled/reloaded core must never block input or lifecycle recovery indefinitely.
	template <typename Clock, typename Sleep, typename Feedback>
	void PaceWithFeedbackClock(std::uint64_t frequency, Clock now, Sleep sleep, Feedback feedback)
	{
		if (frequency == 0)
			return;
		const auto start = now();
		auto sequence = feedback();
		if (feedback_initialized_) {
			while (sequence == feedback_sequence_ && now() - start < frequency / 40) {
				sleep((frequency + 4999) / 5000); // 200 us; yield CPU to audio.
				sequence = feedback();
			}
		}
		if (!feedback_initialized_ || sequence == feedback_sequence_)
			PaceWithClock(frequency, now, sleep);
		else {
			last_ = now();
			deadline_ = last_ + (frequency + 59) / 60;
			initialized_ = true;
		}
		feedback_sequence_ = sequence;
		feedback_initialized_ = true;
	}

	void Reset() { initialized_ = false; last_ = 0; deadline_ = 0; feedback_initialized_ = false; feedback_sequence_ = 0; }
	[[nodiscard]] bool Initialized() const { return initialized_; }
	[[nodiscard]] std::uint64_t Last() const { return last_; }

private:
	bool initialized_ = false;
	std::uint64_t last_ = 0;
	std::uint64_t deadline_ = 0;
	bool feedback_initialized_ = false;
	std::uint32_t feedback_sequence_ = 0;
};

} // namespace diablo::mister::sdl
