#pragma once

#include "transport_input.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdlib>
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
		crc_valid_[slot] = false;
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
		bool pixels_changed = false;
		if (!dirty_copy) {
			CopyIndexedRows(destination.data(), pixels.data(), pitch);
			pixels_changed = true;
		} else if (!shadow_valid_[slot]) {
			CopyIndexedRows(destination.data(), pixels.data(), pitch);
			CopyIndexedRows(pixel_shadows_[slot].data(), pixels.data(), pitch);
			shadow_valid_[slot] = true;
			pixels_changed = true;
		} else {
			// Shared DDR is the measured bottleneck. First build a bounded change
			// summary without touching the destination. This lets a scrolling or
			// otherwise busy frame take one bulk copy before thousands of small
			// uncached writes have already been issued. Sparse frames are replayed
			// as coalesced runs, and every copied range also updates the shadow.
			pixels_changed = SummarizeDirtyFrame(slot, pixels, pitch);
			if (dirty_frame_requires_full_copy_) {
				CopyIndexedRows(destination.data(), pixels.data(), pitch);
				CopyIndexedRows(pixel_shadows_[slot].data(), pixels.data(), pitch);
			} else {
				CopyDirtySummary(destination.data(), pixel_shadows_[slot].data(),
				                pixels, pitch);
			}
		}
		// Each slot owns its palette. Cache the last palette written to this slot
		// so unchanged palettes do not generate another uncached 768-byte write;
		// reset/rebind invalidates every slot below.
		const bool palette_changed = !palette_valid_[slot]
		                             || std::memcmp(last_palettes_[slot].data(), palette_rgb.data(), PALETTE_BYTES) != 0;
		if (palette_changed) {
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
		const bool can_reuse_crc = dirty_copy && crc_valid_[slot]
		                           && !pixels_changed && !palette_changed;
		const std::uint32_t crc = can_reuse_crc
		                             ? last_crcs_[slot]
		                             : Crc32(pixels, pitch, palette_rgb, full_crc);
		last_crcs_[slot] = crc;
		crc_valid_[slot] = true;
		if (!view_.ArmPublishFrameFast(slot, epoch_, frame_id, logic_tick,
	                               frame_id, crc,
	                               full_crc ? FRAME_CHECKSUM_FULL_CRC32 : FRAME_CHECKSUM_SAMPLED_CRC32)) {
			// The slot may still be ARM_WRITING, or an external reset/owner may
			// have changed it while publication was in progress. Do not let a
			// later reuse trust shadow, palette, or CRC state from this failed
			// ownership transition. Reinitialize the slot only through the ABI
			// state machine; leave ownership visible to the caller instead of
			// silently writing another slot.
			(void)InvalidateSlotContentCache(slot);
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

	struct DirtyRowSummary {
		std::uint16_t run_begin = 0;
		std::uint16_t copied_bytes = 0;
		std::uint16_t segments = 0;
		bool changed = false;
		bool whole_row = false;
	};

	struct DirtyRun {
		std::uint16_t start = 0;
		std::uint16_t end = 0;
	};

	static constexpr std::size_t DIRTY_ROW_CHANGE_LIMIT = 64U;
	static constexpr std::size_t DIRTY_COALESCE_GAP = 8U;
	static constexpr std::size_t DIRTY_FULL_FRAME_BYTES = FRAME_PIXEL_BYTES / 2U;
	static constexpr std::size_t DIRTY_FULL_FRAME_SEGMENTS = 2048U;

	// Keep the source-pitch handling in one helper so the bulk and shadow
	// copies take the same path. The shared destination is intentionally only
	// written here after the caller has acquired the slot.
	static void CopyIndexedRows(void *destination_raw, const std::uint8_t *pixels,
	                           std::size_t pitch)
	{
		auto *destination = static_cast<std::uint8_t *>(destination_raw);
		if (pitch == FRAME_WIDTH) {
			std::memcpy(destination, pixels, FRAME_PIXEL_BYTES);
			return;
		}
		for (std::uint32_t row = 0; row < FRAME_HEIGHT; ++row) {
			std::memcpy(destination + static_cast<std::size_t>(row) * FRAME_WIDTH,
			            pixels + static_cast<std::size_t>(row) * pitch,
			            FRAME_WIDTH);
		}
	}

	// Summarize first, then copy. A summary avoids issuing a long prefix of
	// sparse writes before discovering that a scroll changed most of the
	// frame. It also gives the adaptive choice a meaningful byte and transaction
	// estimate without reading back the uncached shared destination.
	[[nodiscard]] bool SummarizeDirtyFrame(std::uint32_t slot,
	                                       std::span<const std::uint8_t> pixels,
	                                       std::size_t pitch)
	{
		dirty_frame_requires_full_copy_ = false;
		dirty_run_count_ = 0;
		std::uint32_t transfer_bytes = 0;
		const auto *shadow = pixel_shadows_[slot].data();
		for (std::uint32_t row = 0; row < FRAME_HEIGHT; ++row) {
			auto &summary = dirty_rows_[row];
			summary = {};
			summary.run_begin = dirty_run_count_;
			const auto *source_row = pixels.data() + static_cast<std::size_t>(row) * pitch;
			const auto *shadow_row = shadow + static_cast<std::size_t>(row) * FRAME_WIDTH;
			if (std::memcmp(source_row, shadow_row, FRAME_WIDTH) == 0) continue;
			summary.changed = true;
			const auto append_run = [&](std::size_t start, std::size_t end) {
				if (dirty_run_count_ >= DIRTY_FULL_FRAME_SEGMENTS) return false;
				dirty_runs_[dirty_run_count_++] = {
				    static_cast<std::uint16_t>(start), static_cast<std::uint16_t>(end)};
				++summary.segments;
				summary.copied_bytes = static_cast<std::uint16_t>(
				    summary.copied_bytes + end - start);
				transfer_bytes += static_cast<std::uint32_t>(end - start);
				return transfer_bytes < DIRTY_FULL_FRAME_BYTES
				       && dirty_run_count_ < DIRTY_FULL_FRAME_SEGMENTS;
			};

			std::size_t column = 0;
			std::size_t pending_start = FRAME_WIDTH;
			std::size_t pending_end = FRAME_WIDTH;
			std::size_t changed = 0;
			while (column < FRAME_WIDTH) {
				while (column < FRAME_WIDTH && source_row[column] == shadow_row[column]) ++column;
				if (column == FRAME_WIDTH) break;
				const std::size_t diff_start = column;
				while (column < FRAME_WIDTH && source_row[column] != shadow_row[column]) {
					++column;
					if (++changed > DIRTY_ROW_CHANGE_LIMIT) {
						summary.whole_row = true;
						break;
					}
				}
				if (summary.whole_row) break;
				const std::size_t diff_end = column;
				if (pending_start == FRAME_WIDTH) {
					pending_start = diff_start;
					pending_end = diff_end;
				} else if (diff_start - pending_end <= DIRTY_COALESCE_GAP) {
					pending_end = diff_end;
				} else {
					if (!append_run(pending_start, pending_end)) {
						dirty_frame_requires_full_copy_ = true;
						return true;
					}
					pending_start = diff_start;
					pending_end = diff_end;
				}
			}
			if (summary.whole_row) {
				// Runs already emitted for this row belong to the now-full row.
				// Roll them back before recording one replacement run.
				dirty_run_count_ = summary.run_begin;
				transfer_bytes -= summary.copied_bytes;
				summary.segments = 0;
				summary.copied_bytes = 0;
				if (!append_run(0, FRAME_WIDTH)) {
					dirty_frame_requires_full_copy_ = true;
					return true;
				}
			} else if (pending_start != FRAME_WIDTH) {
				if (!append_run(pending_start, pending_end)) {
					dirty_frame_requires_full_copy_ = true;
					return true;
				}
			}
		}
		return dirty_run_count_ != 0;
	}

	void CopyDirtySummary(void *destination_raw, std::uint8_t *shadow,
	                      std::span<const std::uint8_t> pixels, std::size_t pitch)
	{
		auto *destination = static_cast<std::uint8_t *>(destination_raw);
		for (std::uint32_t row = 0; row < FRAME_HEIGHT; ++row) {
			const auto &summary = dirty_rows_[row];
			if (!summary.changed) continue;
			const auto *source_row = pixels.data() + static_cast<std::size_t>(row) * pitch;
			auto *destination_row = destination + static_cast<std::size_t>(row) * FRAME_WIDTH;
			auto *shadow_row = shadow + static_cast<std::size_t>(row) * FRAME_WIDTH;
			const auto run_end = static_cast<std::size_t>(summary.run_begin) + summary.segments;
			for (std::size_t run = summary.run_begin; run < run_end; ++run) {
				const auto dirty = dirty_runs_[run];
				const auto start = static_cast<std::size_t>(dirty.start);
				const auto bytes = static_cast<std::size_t>(dirty.end - dirty.start);
				std::memcpy(destination_row + start, source_row + start, bytes);
				std::memcpy(shadow_row + start, source_row + start, bytes);
			}
		}
	}

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
		crc_valid_.fill(false);
		dirty_frame_requires_full_copy_ = false;
	}

	TransportSession(AbiView view, std::uint32_t epoch)
		: view_(view)
		, epoch_(epoch)
		, input_(view, epoch)
	{
		palette_valid_.fill(false);
		shadow_valid_.fill(false);
		crc_valid_.fill(false);
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
	                           std::span<const std::uint8_t> palette, bool full_crc)
	{
		static constexpr auto table = MakeCrcTable();
		std::uint32_t crc = 0xFFFFFFFFU;
		const auto update = [&crc](std::uint8_t value) {
			crc = table[(crc ^ value) & 0xFFU] ^ (crc >> 8U);
		};
		for (std::uint32_t row = 0; row < FRAME_HEIGHT; ++row) {
			const auto *source_row = pixels.data() + static_cast<std::size_t>(row) * pitch;
			if (full_crc) {
				for (std::uint32_t column = 0; column < FRAME_WIDTH; ++column)
					update(source_row[column]);
			} else {
				for (std::uint32_t column = 0; column < FRAME_WIDTH; column += 16U)
					update(source_row[column]);
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
	std::array<std::uint32_t, FRAME_SLOTS> last_crcs_ {};
	std::array<bool, FRAME_SLOTS> crc_valid_ {};
	std::shared_ptr<std::array<std::uint8_t, FRAME_PIXEL_BYTES>[]> pixel_shadows_ =
	    std::make_shared<std::array<std::uint8_t, FRAME_PIXEL_BYTES>[]>(FRAME_SLOTS);
	std::array<bool, FRAME_SLOTS> shadow_valid_ {};
	std::array<DirtyRowSummary, FRAME_HEIGHT> dirty_rows_ {};
	std::array<DirtyRun, DIRTY_FULL_FRAME_SEGMENTS> dirty_runs_ {};
	std::uint16_t dirty_run_count_ = 0;
	bool dirty_frame_requires_full_copy_ = false;
};

} // namespace diablo::mister::transport
