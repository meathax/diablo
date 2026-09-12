#pragma once

#include <SDL.h>

#include <array>
#include <cstdint>

namespace diablo::mister::movie {

constexpr int kFrameWidth = 640;
constexpr int kFrameHeight = 480;

enum class PrepareError {
	None,
	InvalidSurface,
	ScratchAllocation,
	PaletteCopy,
	Clear,
	Scale,
	Lock,
};

struct PreparedFrame {
	SDL_Surface *surface = nullptr;
	SDL_Rect destination {0, 0, 0, 0};
	PrepareError error = PrepareError::None;
	bool approximate_border = false;
};

inline bool IsLandscapeFit(int source_width, int source_height) noexcept
{
	return static_cast<std::int64_t>(source_width) * kFrameHeight
		> static_cast<std::int64_t>(kFrameWidth) * source_height;
}

inline SDL_Rect ComputeDestinationRect(int source_width, int source_height) noexcept
{
	SDL_Rect destination {0, 0, 0, 0};
	if (source_width <= 0 || source_height <= 0) return destination;

	if (IsLandscapeFit(source_width, source_height)) {
		destination.w = kFrameWidth;
		destination.h = static_cast<int>(static_cast<std::int64_t>(source_height) * kFrameWidth
		/ source_width);
	} else {
		destination.w = static_cast<int>(static_cast<std::int64_t>(source_width) * kFrameHeight
		/ source_height);
		destination.h = kFrameHeight;
	}
	destination.x = (kFrameWidth - destination.w) / 2;
	destination.y = (kFrameHeight - destination.h) / 2;
	return destination;
}

enum class CopyResult {
	Success,
	Invalid,
	Lock,
};

// Fixed-size coordinate cache: no allocation and no division in the pixel loop.
// Oversized direct callers retain the original scalar mapping below.
struct NearestIndexedCoordinates {
	std::array<int, kFrameWidth> x;
	std::array<int, kFrameHeight> y;
	int source_width = 0, source_height = 0;
	int destination_width = 0, destination_height = 0;

	bool Prepare(int sw, int sh, int dw, int dh) noexcept
	{
		if (dw > kFrameWidth || dh > kFrameHeight) return false;
		if (sw == source_width && sh == source_height
			&& dw == destination_width && dh == destination_height) return true;
		auto fill = [](auto &coordinates, int source_size, int destination_size) {
			for (int i = 0; i < destination_size; ++i) {
				const auto numerator = (std::uint64_t {2} * i + 1) * source_size;
				const int index = static_cast<int>(numerator / (std::uint64_t {2} * destination_size));
				coordinates[i] = index < source_size ? index : source_size - 1;
			}
		};
		fill(x, sw, dw);
		fill(y, sh, dh);
		source_width = sw;
		source_height = sh;
		destination_width = dw;
		destination_height = dh;
		return true;
	}
};

inline CopyResult CopyNearestIndexed(SDL_Surface *source, SDL_Surface *destination,
	const SDL_Rect &destination_rect, std::uint8_t border_index,
	NearestIndexedCoordinates *cached_coordinates = nullptr) noexcept
{
	if (source == nullptr || destination == nullptr || source->pixels == nullptr
		|| destination->pixels == nullptr || destination_rect.x < 0 || destination_rect.y < 0
		|| destination_rect.w <= 0 || destination_rect.h <= 0
		|| destination_rect.x + destination_rect.w > destination->w
		|| destination_rect.y + destination_rect.h > destination->h) {
		return CopyResult::Invalid;
	}

	const bool source_locked = SDL_MUSTLOCK(source) != 0;
	if (source_locked && SDL_LockSurface(source) != 0) return CopyResult::Lock;
	const bool destination_locked = SDL_MUSTLOCK(destination) != 0;
	if (destination_locked && SDL_LockSurface(destination) != 0) {
		if (source_locked) SDL_UnlockSurface(source);
		return CopyResult::Lock;
	}

	const auto *source_pixels = static_cast<const std::uint8_t *>(source->pixels);
	auto *destination_pixels = static_cast<std::uint8_t *>(destination->pixels);
	for (int y = 0; y < destination->h; ++y) {
		auto *destination_row = destination_pixels + y * destination->pitch;
		for (int x = 0; x < destination->w; ++x) destination_row[x] = border_index;
	}
	NearestIndexedCoordinates local_coordinates;
	auto &coordinates = cached_coordinates != nullptr ? *cached_coordinates : local_coordinates;
	const bool mapped = coordinates.Prepare(source->w, source->h, destination_rect.w, destination_rect.h);
	for (int y = 0; y < destination_rect.h; ++y) {
		if (mapped) {
			const auto *source_row = source_pixels + coordinates.y[y] * source->pitch;
			auto *destination_row = destination_pixels
				+ (destination_rect.y + y) * destination->pitch + destination_rect.x;
			for (int x = 0; x < destination_rect.w; ++x)
				destination_row[x] = source_row[coordinates.x[x]];
			continue;
		}
		const auto source_y_numerator
			= (static_cast<std::uint64_t>(2) * static_cast<std::uint64_t>(y) + 1)
			* static_cast<std::uint64_t>(source->h);
		const int source_y_unclamped = static_cast<int>(source_y_numerator
			/ (static_cast<std::uint64_t>(2) * static_cast<std::uint64_t>(destination_rect.h)));
		const int source_y = source_y_unclamped < source->h ? source_y_unclamped : source->h - 1;
		const auto *source_row = source_pixels + source_y * source->pitch;
		auto *destination_row = destination_pixels
			+ (destination_rect.y + y) * destination->pitch + destination_rect.x;
		for (int x = 0; x < destination_rect.w; ++x) {
			const auto source_x_numerator
				= (static_cast<std::uint64_t>(2) * static_cast<std::uint64_t>(x) + 1)
				* static_cast<std::uint64_t>(source->w);
			const int source_x_unclamped = static_cast<int>(source_x_numerator
				/ (static_cast<std::uint64_t>(2) * static_cast<std::uint64_t>(destination_rect.w)));
			const int source_x = source_x_unclamped < source->w ? source_x_unclamped : source->w - 1;
			destination_row[x] = source_row[source_x];
		}
	}

	if (destination_locked) SDL_UnlockSurface(destination);
	if (source_locked) SDL_UnlockSurface(source);
	return CopyResult::Success;
}

class IndexedFrameAdapter {
public:
	IndexedFrameAdapter() = default;
	~IndexedFrameAdapter()
	{
		if (scratch_ != nullptr) SDL_FreeSurface(scratch_);
	}

	IndexedFrameAdapter(const IndexedFrameAdapter &) = delete;
	IndexedFrameAdapter &operator=(const IndexedFrameAdapter &) = delete;

	PreparedFrame Prepare(SDL_Surface *source)
	{
		PreparedFrame prepared;
		if (source == nullptr || source->pixels == nullptr || source->format == nullptr
			|| source->format->BitsPerPixel != 8 || source->format->palette == nullptr
			|| source->format->palette->ncolors != 256 || source->w <= 0 || source->h <= 0
			|| source->pitch < source->w) {
			prepared.error = PrepareError::InvalidSurface;
			return prepared;
		}

		if (source->w == kFrameWidth && source->h == kFrameHeight && source->pitch >= kFrameWidth) {
			prepared.surface = source;
			prepared.destination = {0, 0, kFrameWidth, kFrameHeight};
			return prepared;
		}

		if (scratch_ == nullptr) {
			scratch_ = SDL_CreateRGBSurfaceWithFormat(0, kFrameWidth, kFrameHeight, 8, SDL_PIXELFORMAT_INDEX8);
			if (scratch_ == nullptr) {
				prepared.error = PrepareError::ScratchAllocation;
				return prepared;
			}
		}
		if (scratch_->format == nullptr || scratch_->format->palette == nullptr
			|| scratch_->pitch < kFrameWidth) {
			prepared.error = PrepareError::ScratchAllocation;
			return prepared;
		}

		if (SDL_SetPaletteColors(scratch_->format->palette, source->format->palette->colors, 0, 256) != 0) {
			prepared.error = PrepareError::PaletteCopy;
			return prepared;
		}

		const auto border_index = static_cast<std::uint8_t>(SDL_MapRGB(scratch_->format, 0, 0, 0));
		const auto border_color = scratch_->format->palette->colors[border_index];
		prepared.approximate_border = border_color.r != 0 || border_color.g != 0 || border_color.b != 0;

		prepared.destination = ComputeDestinationRect(source->w, source->h);
		if (prepared.destination.w <= 0 || prepared.destination.h <= 0) {
			prepared.error = PrepareError::Scale;
			return prepared;
		}
		const auto copy_result = CopyNearestIndexed(source, scratch_, prepared.destination, border_index, &coordinates_);
		if (copy_result != CopyResult::Success) {
			prepared.error = copy_result == CopyResult::Lock ? PrepareError::Lock : PrepareError::Scale;
			return prepared;
		}

		prepared.surface = scratch_;
		return prepared;
	}

	bool ConsumeApproximateBorderNotice(bool approximate) noexcept
	{
		if (!approximate || approximate_border_reported_) return false;
		approximate_border_reported_ = true;
		return true;
	}

	bool ConsumeErrorNotice() noexcept
	{
		if (error_reported_) return false;
		error_reported_ = true;
		return true;
	}

private:
	NearestIndexedCoordinates coordinates_;
	SDL_Surface *scratch_ = nullptr;
	bool approximate_border_reported_ = false;
	bool error_reported_ = false;
};

} // namespace diablo::mister::movie
