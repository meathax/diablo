#pragma once

#include <SDL.h>

#include <chrono>
#include <cstdint>
#include <thread>

namespace diablo::mister::sdl {

// Sleep on a high-resolution clock. Rebase on actual wake-up so slow frames
// never cause catch-up bursts into the FPGA queue. Independent of SDL display Hz.
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
		if (initialized_) {
			const auto period = (frequency + 59) / 60;
			while (current - last_ < period) {
				sleep(period - (current - last_));
				current = now();
			}
		}
		initialized_ = true;
		last_ = current;
	}

	void Reset() { initialized_ = false; last_ = 0; }
	[[nodiscard]] bool Initialized() const { return initialized_; }
	[[nodiscard]] std::uint64_t Last() const { return last_; }

private:
	bool initialized_ = false;
	std::uint64_t last_ = 0;
};

} // namespace diablo::mister::sdl
