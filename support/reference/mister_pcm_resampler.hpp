// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>

namespace diablo::mister::sdl {

// Single audio-callback owner. No allocation, transport access or blocking.
// Returned storage remains valid until the next Convert call. The lifecycle
// thread requests reset by generation; only the callback mutates this state.
class PcmResampler {
public:
 using PcmFrame = std::array<std::int16_t, 2>;
 [[nodiscard]] std::optional<std::span<const std::byte>> Convert(
     const std::uint8_t *bytes, std::size_t byte_count, std::uint32_t generation)
 {
  if (bytes == nullptr || byte_count < 4 || (byte_count & 3U) != 0)
   return std::nullopt;
		if (resample_generation_ != generation) {
			resample_position_ = 0;
			resample_have_previous_ = false;
			resample_generation_ = generation;
		}
		const std::size_t source_frames = byte_count / 4U;
		if (source_frames > kMaxSourceFrames) return std::nullopt;
		for (std::size_t index = 0; index < source_frames; ++index) {
			const std::size_t byte_offset = index * 4U;
			const auto left = static_cast<std::uint16_t>(bytes[byte_offset + 0U])
			               | static_cast<std::uint16_t>(bytes[byte_offset + 1U]) << 8U;
			const auto right = static_cast<std::uint16_t>(bytes[byte_offset + 2U])
			                | static_cast<std::uint16_t>(bytes[byte_offset + 3U]) << 8U;
			resample_input_[index] = {
				static_cast<std::int16_t>(left), static_cast<std::int16_t>(right)};
		}

		const bool had_previous = resample_have_previous_;
		if (!had_previous) {
			resample_previous_ = resample_input_[0];
			resample_have_previous_ = true;
		}
		const std::size_t combined_frames = had_previous ? source_frames + 1U : source_frames;
		const std::uint64_t last_index = static_cast<std::uint64_t>(combined_frames - 1U);
		const std::uint64_t end_position = last_index << kPhaseBits;
		std::size_t output_frames = 0;
		while (resample_position_ < end_position) {
			if (output_frames >= kMaxOutputFrames) return std::nullopt;
			const std::size_t index = static_cast<std::size_t>(resample_position_ >> kPhaseBits);
			const std::uint32_t fraction = static_cast<std::uint32_t>(
				resample_position_ & kPhaseMask);
			const PcmFrame &first = had_previous
				? (index == 0 ? resample_previous_ : resample_input_[index - 1U])
				: resample_input_[index];
			const PcmFrame &second = had_previous
				? resample_input_[index]
				: resample_input_[index + 1U];
			const auto left = Interpolate(first[0], second[0], fraction);
			const auto right = Interpolate(first[1], second[1], fraction);
			const std::size_t byte_offset = output_frames * 4U;
			resample_output_[byte_offset + 0U] = static_cast<std::byte>(
				static_cast<std::uint16_t>(left) & 0xffU);
			resample_output_[byte_offset + 1U] = static_cast<std::byte>(
				static_cast<std::uint16_t>(left) >> 8U);
			resample_output_[byte_offset + 2U] = static_cast<std::byte>(
				static_cast<std::uint16_t>(right) & 0xffU);
			resample_output_[byte_offset + 3U] = static_cast<std::byte>(
				static_cast<std::uint16_t>(right) >> 8U);
			++output_frames;
			resample_position_ += kPhaseStep;
		}
		resample_previous_ = resample_input_[source_frames - 1U];
		resample_position_ -= end_position;
  return std::span<const std::byte>(resample_output_.data(), output_frames * 4U);
 }
private:
	static constexpr unsigned kPhaseBits = 32;
	static constexpr std::uint64_t kPhaseMask = (1ULL << kPhaseBits) - 1ULL;
	static constexpr std::uint32_t kPcmSourceRate = 22050;
	static constexpr std::uint32_t kPcmOutputRate = 48000;
	static constexpr std::uint64_t kPhaseStep =
		(static_cast<std::uint64_t>(kPcmSourceRate) << kPhaseBits) / kPcmOutputRate;
	static constexpr std::size_t kMaxSourceFrames = 8192;
	static constexpr std::size_t kMaxOutputFrames = 18432;

	static std::int16_t Interpolate(std::int16_t first, std::int16_t second,
	                                std::uint32_t fraction)
	{
		const auto first_weight = static_cast<std::int64_t>(kPhaseMask + 1U - fraction);
		const auto second_weight = static_cast<std::int64_t>(fraction);
		const auto value = static_cast<std::int64_t>(first) * first_weight
		                 + static_cast<std::int64_t>(second) * second_weight;
		return static_cast<std::int16_t>(value >> kPhaseBits);
	}

	std::uint32_t resample_generation_ = 0;
	std::array<PcmFrame, kMaxSourceFrames> resample_input_ {};
	std::array<std::byte, kMaxOutputFrames * 4U> resample_output_ {};
	PcmFrame resample_previous_ {};
	std::uint64_t resample_position_ = 0;
	bool resample_have_previous_ = false;
};
} // namespace diablo::mister::sdl
