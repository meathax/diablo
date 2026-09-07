#pragma once

#include "mister_command_renderer.hpp"
#include "transport_abi.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>

namespace diablo::mister::command {

// Convert changed pixels in one indexed scene into bounded FillRect
// rectangles. Identical horizontal runs on adjacent rows are coalesced
// vertically, while the two fixed run arrays are swapped by pointer so the ARM
// does not copy 640 entries every row. If the fixed record budget is exceeded,
// the caller falls back to the complete indexed-frame publisher.
[[nodiscard]] inline bool BuildChangedRuns(
    Buffer &commands,
    std::span<const std::uint8_t> source,
    std::size_t source_pitch,
	std::span<const std::uint8_t> shadow,
	std::uint32_t target_slot)
{
	constexpr std::size_t last_row = transport::FRAME_HEIGHT - 1U;
	if (target_slot >= transport::FRAME_SLOTS
	    || source_pitch < transport::FRAME_WIDTH
	    || source_pitch > (std::numeric_limits<std::size_t>::max() - transport::FRAME_WIDTH) / last_row
	    || source.size() < last_row * source_pitch + transport::FRAME_WIDTH
    || shadow.size() < transport::FRAME_PIXEL_BYTES)
		return false;
	struct PendingRun {
		std::uint32_t x;
		std::uint32_t width;
		std::uint32_t y;
		std::uint32_t height;
		std::uint8_t colour;
		bool continued;
	};
	std::array<PendingRun, transport::FRAME_WIDTH> runs_a {};
	std::array<PendingRun, transport::FRAME_WIDTH> runs_b {};
	auto *previous = &runs_a;
	auto *current = &runs_b;
	std::array<std::int16_t, transport::FRAME_WIDTH> previous_by_x {};
	std::array<std::uint32_t, transport::FRAME_WIDTH> map_generation {};
	// A zero-initialized generation is row zero, so it cannot also mean "no
	// run at this x". Otherwise a changed pixel on row one can accidentally
	// extend runs_a[0] even when the previous row had no run at that column.
	previous_by_x.fill(-1);
	map_generation.fill(~std::uint32_t { 0 });
	std::size_t previous_count = 0;
	for (std::uint32_t row = 0; row < transport::FRAME_HEIGHT; ++row) {
		const auto *source_row = source.data() + static_cast<std::size_t>(row) * source_pitch;
		const auto *shadow_row = shadow.data() + row * transport::FRAME_WIDTH;
		for (std::size_t index = 0; index < previous_count; ++index)
			(*previous)[index].continued = false;
		std::size_t current_count = 0;
		std::uint32_t column = 0;
		while (column < transport::FRAME_WIDTH) {
			while (column < transport::FRAME_WIDTH
			       && source_row[column] == shadow_row[column])
				++column;
			if (column == transport::FRAME_WIDTH) break;
			const std::uint32_t start = column;
			const std::uint8_t colour = source_row[column];
			++column;
			while (column < transport::FRAME_WIDTH
			       && source_row[column] != shadow_row[column]
			       && source_row[column] == colour)
				++column;
			const std::uint32_t width = column - start;
			const std::int16_t previous_index = previous_by_x[start];
			const bool matches_previous = row != 0
				&& map_generation[start] == row - 1U
				&& previous_index >= 0
				&& static_cast<std::size_t>(previous_index) < previous_count
				&& (*previous)[previous_index].x == start
				&& !(*previous)[previous_index].continued
				&& (*previous)[previous_index].width == width
				&& (*previous)[previous_index].colour == colour;
			if (current_count == current->size()) return false;
			if (matches_previous) {
				const auto &candidate = (*previous)[previous_index];
				(*current)[current_count] = {
					candidate.x, candidate.width, candidate.y, candidate.height + 1U,
					candidate.colour, false,
				};
				(*previous)[previous_index].continued = true;
			} else {
				(*current)[current_count] = { start, width, row, 1, colour, false };
			}
			previous_by_x[start] = static_cast<std::int16_t>(current_count);
			map_generation[start] = row;
			++current_count;
		}
		for (std::size_t index = 0; index < previous_count; ++index) {
			const auto &run = (*previous)[index];
			if (run.continued) continue;
			if (!commands.FillRectToSlot(
			        static_cast<std::int32_t>(run.x),
			        static_cast<std::int32_t>(run.y),
			        static_cast<std::int32_t>(run.width),
			        static_cast<std::int32_t>(run.height), run.colour, target_slot))
				return false;
		}
		std::swap(previous, current);
		previous_count = current_count;
	}
	for (std::size_t index = 0; index < previous_count; ++index) {
		const auto &run = (*previous)[index];
		if (!commands.FillRectToSlot(
		        static_cast<std::int32_t>(run.x),
		        static_cast<std::int32_t>(run.y),
		        static_cast<std::int32_t>(run.width),
		        static_cast<std::int32_t>(run.height), run.colour, target_slot))
			return false;
	}
	return true;
}

} // namespace diablo::mister::command
