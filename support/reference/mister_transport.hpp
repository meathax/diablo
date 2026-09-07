#pragma once

#include "transport_input.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <expected>
#include <limits>
#include <memory>
#include <span>


namespace diablo::mister::transport {

class TransportRuntime;

enum class PublishError : std::uint32_t {
	BadLayout,
	BadPixels,
	BadPalette,
	Backpressure,
};

// Small ARM-side session facade. It deliberately accepts a prepared indexed
// surface instead of depending on SDL, so the engine presentation adapter can
// be tested with the same memory ordering and ownership rules as the target.
class TransportSession {
public:
	static std::expected<TransportSession, AttachError> Attach(
	    std::span<std::byte> memory, std::uint32_t epoch)
	{
		auto view = AbiView::Attach(memory);
		if (!view.has_value()) return std::unexpected(view.error());
		if (!view->InitializeArm(epoch)) return std::unexpected(AttachError::StaleEpoch);
		return TransportSession(*view, epoch);
	}

	[[nodiscard]] AbiView view() const { return view_; }
	[[nodiscard]] std::uint32_t epoch() const { return epoch_; }
	[[nodiscard]] const InputConsumer &input() const { return input_; }
	[[nodiscard]] InputConsumer &input() { return input_; }
	[[nodiscard]] std::uint64_t AllocateFrameId() { return next_frame_id_++; }

	// The command renderer can update slot pixels and palette bytes directly in
	// shared DDR. Do not let a later full or dirty copy trust ARM-side content
	// cached before that external write completed.
	[[nodiscard]] bool InvalidateSlotContentCache(std::uint32_t slot)
	{
		if (slot >= FRAME_SLOTS) return false;
		palette_valid_[slot] = false;
		shadow_valid_[slot] = false;
		return true;
	}

	// Publishes one complete indexed 640x480 frame. The caller owns pacing; this
	// method only accepts a free slot and never reuses a displayed or in-flight
	// slot. A full three-slot pipeline returns Backpressure immediately, which
	// keeps stale frames from accumulating behind scanout.
	[[nodiscard]] std::expected<std::uint64_t, PublishError> PublishIndexedFrame(
	    std::span<const std::uint8_t> pixels, std::size_t pitch,
	    std::span<const std::uint8_t> palette_rgb, std::uint64_t logic_tick)
	{
		constexpr std::size_t last_row = FRAME_HEIGHT - 1U;
		if (pitch < FRAME_WIDTH
		    || pitch > (std::numeric_limits<std::size_t>::max() - FRAME_WIDTH) / last_row
		    || pixels.size() < last_row * pitch + FRAME_WIDTH)
			return std::unexpected(PublishError::BadPixels);
		if (palette_rgb.size() != PALETTE_BYTES)
			return std::unexpected(PublishError::BadPalette);

		std::uint32_t slot = 0;
		bool acquired = false;
		for (std::uint32_t attempt = 0; attempt < FRAME_SLOTS; ++attempt) {
			const std::uint32_t candidate = (next_slot_ + attempt) % FRAME_SLOTS;
			if (view_.ArmBeginFrameFast(candidate, epoch_).has_value()) {
				slot = candidate;
				next_slot_ = (candidate + 1U) % FRAME_SLOTS;
				acquired = true;
				break;
			}
		}
		if (!acquired) return std::unexpected(PublishError::Backpressure);

		const FrameSlot &descriptor = view_.header().frames[slot];
		auto destination = view_.memory().subspan(descriptor.pixel_offset, descriptor.pixel_bytes);
		const bool dirty_copy = DirtyCopyEnabled();
		if (!dirty_copy) {
			if (pitch == FRAME_WIDTH) {
				std::memcpy(destination.data(), pixels.data(), FRAME_PIXEL_BYTES);
			} else {
				for (std::uint32_t row = 0; row < FRAME_HEIGHT; ++row) {
					std::memcpy(destination.data() + row * FRAME_WIDTH,
					            pixels.data() + static_cast<std::size_t>(row) * pitch,
					            FRAME_WIDTH);
				}
			}
		} else if (!shadow_valid_[slot]) {
			for (std::uint32_t row = 0; row < FRAME_HEIGHT; ++row) {
				const auto *source_row = pixels.data() + static_cast<std::size_t>(row) * pitch;
				std::memcpy(destination.data() + row * FRAME_WIDTH, source_row, FRAME_WIDTH);
				std::memcpy(pixel_shadows_[slot].data() + row * FRAME_WIDTH,
				            source_row, FRAME_WIDTH);
			}
			shadow_valid_[slot] = true;
		} else {
			// Shared DDR is the measured bottleneck. Compare against this slot's
			// cached source image and write only changed contiguous runs, while
			// keeping the complete shadow current for the next reuse.
			for (std::uint32_t row = 0; row < FRAME_HEIGHT; ++row) {
				const auto *source_row = pixels.data() + static_cast<std::size_t>(row) * pitch;
				auto *shadow_row = pixel_shadows_[slot].data() + row * FRAME_WIDTH;
				if (std::memcmp(source_row, shadow_row, FRAME_WIDTH) == 0) continue;
				std::size_t column = 0;
				std::size_t changed = 0;
				while (column < FRAME_WIDTH) {
					while (column < FRAME_WIDTH && source_row[column] == shadow_row[column]) ++column;
					const std::size_t start = column;
					while (column < FRAME_WIDTH && source_row[column] != shadow_row[column]) {
						shadow_row[column] = source_row[column];
						++column;
						if (++changed > 64) break;
					}
					if (changed > 64) {
						std::memcpy(destination.data() + row * FRAME_WIDTH, source_row, FRAME_WIDTH);
						std::memcpy(shadow_row, source_row, FRAME_WIDTH);
						break;
					}
					if (column != start)
						std::memcpy(destination.data() + row * FRAME_WIDTH + start,
						            source_row + start, column - start);
				}
			}
		}
		// Each slot owns its palette. Cache the last palette written to this slot
		// so unchanged palettes do not generate another uncached 768-byte write;
		// reset/rebind invalidates every slot below.
		if (!palette_valid_[slot]
		    || std::memcmp(last_palettes_[slot].data(), palette_rgb.data(), PALETTE_BYTES) != 0) {
			std::memcpy(view_.memory().data() + descriptor.palette_offset,
			            palette_rgb.data(), PALETTE_BYTES);
			std::memcpy(last_palettes_[slot].data(), palette_rgb.data(), PALETTE_BYTES);
			palette_valid_[slot] = true;
		}

		const std::uint64_t frame_id = next_frame_id_++;
		// Calculate the diagnostic checksum from cached ARM-side source pixels.
		// Reading the just-written /dev/mem slot back on every frame is much
		// slower than the copy itself and provides no ordering guarantee.
		const bool full_crc = FullCrcEnabled();
		const std::uint32_t crc = Crc32(pixels, pitch, palette_rgb);
		if (!view_.ArmPublishFrameFast(slot, epoch_, frame_id, logic_tick,
	                               frame_id, crc,
	                               full_crc ? FRAME_CHECKSUM_FULL_CRC32 : FRAME_CHECKSUM_SAMPLED_CRC32)) {
			// Reinitialize the slot only through the ABI state machine. A failed
			// publication is a transport fault; leave ownership visible to the
			// caller instead of silently writing another slot.
			return std::unexpected(PublishError::BadLayout);
		}
		return frame_id;
	}

	[[nodiscard]] std::expected<std::size_t, AttachError> PollInput(
	    std::span<InputEvent> scratch)
	{
		return input_.Poll(scratch);
	}

	[[nodiscard]] InputSnapshot TakeInputSnapshot() { return input_.TakeSnapshot(); }
	[[nodiscard]] std::expected<PcmHealth, AttachError> ReadPcmHealth() const
	{
		return view_.ReadPcmHealth(epoch_);
	}

private:
	friend class TransportRuntime;

	// A MiSTer core reset can invalidate in-flight frame descriptors while the
	// ARM process remains alive. Rebinding the same mapping to a fresh epoch
	// gives the FPGA control reader a clean ownership slate without reopening
	// /dev/mem or losing the engine's SDL instance.
	void RebindEpoch(std::uint32_t epoch)
	{
		epoch_ = epoch;
		input_ = InputConsumer(view_, epoch);
		next_slot_ = 0;
		next_frame_id_ = 1;
		palette_valid_.fill(false);
		shadow_valid_.fill(false);
	}

	TransportSession(AbiView view, std::uint32_t epoch)
		: view_(view)
		, epoch_(epoch)
		, input_(view, epoch)
	{
		shadow_valid_.fill(false);
	}

	static constexpr std::array<std::uint32_t, 256> MakeCrcTable()
	{
		std::array<std::uint32_t, 256> table {};
		for (std::uint32_t index = 0; index < table.size(); ++index) {
			std::uint32_t value = index;
			for (unsigned bit = 0; bit < 8; ++bit)
				value = (value >> 1U) ^ (0xEDB88320U & static_cast<std::uint32_t>(-
				    static_cast<std::int32_t>(value & 1U)));
			table[index] = value;
		}
		return table;
	}

	static std::uint32_t Crc32(std::span<const std::uint8_t> pixels, std::size_t pitch,
	                           std::span<const std::uint8_t> palette)
	{
		static constexpr auto table = MakeCrcTable();
		const bool full_crc = FullCrcEnabled();
		std::uint32_t crc = 0xFFFFFFFFU;
		const auto update = [&crc](std::uint8_t value) {
			crc = table[(crc ^ value) & 0xFFU] ^ (crc >> 8U);
		};
		for (std::uint32_t row = 0; row < FRAME_HEIGHT; ++row) {
			for (std::uint32_t column = 0; column < FRAME_WIDTH; ++column) {
				if (full_crc || ((column & 15U) == 0U))
					update(pixels[static_cast<std::size_t>(row) * pitch + column]);
			}
		}
		for (const std::uint8_t value : palette)
			update(value);
		return ~crc;
	}

	static bool FullCrcEnabled()
	{
		static const bool enabled = [] {
			const char *value = std::getenv("DIABLO_MISTER_FULL_CRC");
			return value != nullptr && (std::strcmp(value, "1") == 0
			                            || std::strcmp(value, "true") == 0);
		}();
		return enabled;
	}

	static bool DirtyCopyEnabled()
	{
		static const bool enabled = [] {
			const char *value = std::getenv("DIABLO_MISTER_DIRTY_COPY");
			return value != nullptr && (std::strcmp(value, "1") == 0
			                            || std::strcmp(value, "true") == 0);
		}();
		return enabled;
	}

	AbiView view_;
	std::uint32_t epoch_;
	InputConsumer input_;
	std::uint32_t next_slot_ = 0;
	std::uint64_t next_frame_id_ = 1;
	std::array<std::array<std::uint8_t, PALETTE_BYTES>, FRAME_SLOTS> last_palettes_ {};
	std::array<bool, FRAME_SLOTS> palette_valid_ {};
	std::shared_ptr<std::array<std::uint8_t, FRAME_PIXEL_BYTES>[]> pixel_shadows_ =
	    std::make_shared<std::array<std::uint8_t, FRAME_PIXEL_BYTES>[]>(FRAME_SLOTS);
	std::array<bool, FRAME_SLOTS> shadow_valid_ {};
};

} // namespace diablo::mister::transport
