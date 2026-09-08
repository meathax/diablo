// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "transport_abi.hpp"
#include "mister_transport_runtime.hpp"
#include "mister_command_scene.hpp"
#include "mister_command_transport.hpp"
#include "mister_transport_profiler.hpp"
#include <atomic>
#include <cstring>
#include <optional>
#include <span>
#include <array>
#include <cstdint>
#include <memory>

namespace diablo::mister::sdl {

// Main-thread state for the command writer and its per-slot pixel shadows.
// Runtime ownership is borrowed for each operation. Reset is permitted only after
// lifecycle quiescence or epoch rebind, never to recycle a timed-out live slot.
class CommandFrameState {
public:
 CommandFrameState() = default;
 CommandFrameState(const CommandFrameState &) = delete;
 CommandFrameState &operator=(const CommandFrameState &) = delete;
	void Reset()
	{
		command_shadow_valid_.fill(false);
		command_next_slot_ = 0;
		command_attempt_fence_ = 1;
		command_submission_ = {};
		command_scene_faulted_ = false;
	}

	void FaultCommandSubmission(transport::AbiView view, TransportProfiler &profile_)
	{
		if (!command_submission_.active) return;
		// Commands may still be reaching the DDR writer after the deadline. Keep
		// the slot out of FREE/READY so a late write cannot damage a recycled
		// frame, and let the control reader detach this epoch through arm_state.
		(void)view.ArmFaultFrameFast(command_submission_.slot, command_submission_.epoch);
		view.SignalFault(transport::FAULT_COMMAND_FENCE_TIMEOUT,
		                 command_submission_.slot);
		command_shadow_valid_[command_submission_.slot] = false;
		command_submission_.timed_out = true;
		command_scene_faulted_ = true;
		++profile_.command_scene_fence_failures_;
	}

	void RecordCommandWait(std::uint64_t now, TransportProfiler &profile_)
	{
		auto &submission = command_submission_;
		if (submission.wait_recorded || submission.submitted_ns == 0
		    || now < submission.submitted_ns) return;
		const auto elapsed = now - submission.submitted_ns;
		++profile_.command_wait_count_;
		profile_.command_wait_total_ns_ += elapsed;
		profile_.command_wait_max_ns_ = std::max(profile_.command_wait_max_ns_, elapsed);
		submission.wait_recorded = true;
	}

	void ReconcileCommandSubmission(const std::shared_ptr<transport::TransportRuntime> &runtime, TransportProfiler &profile_)
	{
		if (!command_submission_.active || !runtime) return;
		auto view = runtime->session().view();
		if (runtime->session().epoch() != command_submission_.epoch) {
			// RebindEpoch invalidates the TransportSession caches and resets every
			// ABI slot. The adapter's command shadows must be invalidated too or a
			// post-reset changed-run command could skip pixels that are now zero.
			Reset();
			return;
		}
		std::atomic_ref<std::uint64_t> completed(view.header().last_completed_fence);
		if (completed.load(std::memory_order_acquire) == command_submission_.fence) {
			if (!command_submission_.timed_out) {
				if (view.ArmPublishFrameFast(command_submission_.slot, command_submission_.epoch,
				                             command_submission_.frame_id, command_submission_.logic_tick,
				                             command_submission_.fence, 0, transport::FRAME_CHECKSUM_ABSENT)) {
					command_shadow_valid_[command_submission_.slot] = true;
					++profile_.command_scene_batches_;
				} else {
					FaultCommandSubmission(view, profile_);
				}
			}
			if (profile_.ProfileEnabled()) RecordCommandWait(profile_.NowNs(), profile_);
			command_submission_.active = false;
			return;
		}
		if (!command_submission_.timed_out && profile_.NowNs() >= command_submission_.deadline_ns) {
			FaultCommandSubmission(view, profile_);
			if (profile_.ProfileEnabled()) RecordCommandWait(profile_.NowNs(), profile_);
		}
	}

	[[nodiscard]] std::optional<bool> TryPresentCommand(
	    std::span<const std::uint8_t> source, std::size_t source_pitch,
	    std::span<const std::uint8_t> palette, std::uint64_t logic_tick,
	    const std::shared_ptr<transport::TransportRuntime> &runtime, TransportProfiler &profile_, unsigned wait_ms)
	{
		if (!runtime) return std::nullopt;
		ReconcileCommandSubmission(runtime, profile_);
		if (command_submission_.active || command_scene_faulted_) return std::nullopt;
		++profile_.command_scene_attempts_;
		auto view = runtime->session().view();
		const std::uint32_t epoch = runtime->session().epoch();
		std::uint32_t slot = 0;
		bool acquired = false;
		for (std::uint32_t attempt = 0; attempt < transport::FRAME_SLOTS; ++attempt) {
			const std::uint32_t candidate = (command_next_slot_ + attempt) % transport::FRAME_SLOTS;
			if (!command_shadow_valid_[candidate]) continue;
			if (view.ArmBeginFrameFast(candidate, epoch).has_value()) {
				slot = candidate;
				command_next_slot_ = (candidate + 1U) % transport::FRAME_SLOTS;
				acquired = true;
				break;
			}
		}
		if (!acquired) {
			++profile_.command_scene_no_slot_;
			return std::nullopt;
		}

		command::Buffer commands;
		const std::uint64_t command_build_start = profile_.ProfileEnabled() ? profile_.NowNs() : 0;
		const auto shadow = std::span<const std::uint8_t>(
			command_shadows_[slot].data(), transport::FRAME_PIXEL_BYTES);
		const std::uint64_t fence = command_attempt_fence_ == 0 ? 1 : command_attempt_fence_;
		command_attempt_fence_ = fence + 1U;
		if (command_attempt_fence_ == 0) command_attempt_fence_ = 1;
		if (!command::BuildChangedRuns(commands, source, source_pitch, shadow, slot)) {
			++profile_.command_scene_overflow_;
			(void)view.ArmAbortFrameFast(slot, epoch);
			return std::nullopt;
		}
		if (!commands.End(fence)) {
			++profile_.command_scene_overflow_;
			(void)view.ArmAbortFrameFast(slot, epoch);
			return std::nullopt;
		}
		if (profile_.ProfileEnabled() && command_build_start != 0)
			profile_.RecordCommandBuild(command_build_start, profile_.NowNs());

		// The command path writes this slot's palette here and its pixels through
		// the FPGA. Invalidate TransportSession's full/dirty-copy caches before
		// either write is visible so a later fallback cannot skip stale bytes.
		if (!runtime->session().InvalidateSlotContentCache(slot)) {
			++profile_.command_scene_publish_failures_;
			(void)view.ArmAbortFrameFast(slot, epoch);
			return std::nullopt;
		}
		const auto &descriptor = view.header().frames[slot];
		std::memcpy(view.memory().data() + descriptor.palette_offset,
		            palette.data(), transport::PALETTE_BYTES);
		command::Publisher publisher(view, epoch);
		const auto published = publisher.Publish(commands.records(), {});
		if (!published.has_value()) {
			++profile_.command_scene_publish_failures_;
			(void)view.ArmAbortFrameFast(slot, epoch);
			return std::nullopt;
		}
		const std::uint64_t frame_id = runtime->session().AllocateFrameId();
		for (std::uint32_t row = 0; row < transport::FRAME_HEIGHT; ++row)
			std::memcpy(command_shadows_[slot].data() + row * transport::FRAME_WIDTH,
			            source.data() + static_cast<std::size_t>(row) * source_pitch,
			            transport::FRAME_WIDTH);
		command_submission_ = {
			.active = true,
			.timed_out = false,
			.slot = slot,
			.epoch = epoch,
			.fence = fence,
			.frame_id = frame_id,
			.logic_tick = logic_tick,
			.submitted_ns = profile_.NowNs(),
			.deadline_ns = profile_.NowNs() + static_cast<std::uint64_t>(wait_ms) * 1'000'000U,
		};
		if (!runtime->Flush()) {
			FaultCommandSubmission(view, profile_);
			return std::nullopt;
		}
		// Fence completion is serviced by future Present calls. Returning nullopt
		// lets the established full-frame producer use another free slot instead
		// of blocking the engine thread for the entire recovery interval.
		return std::nullopt;
	}

	void RememberFullFrame(std::uint64_t frame_id, std::span<const std::uint8_t> source,
	                       std::size_t source_pitch, const std::shared_ptr<transport::TransportRuntime> &runtime)
	{
		if (!runtime) return;
		auto view = runtime->session().view();
		for (std::uint32_t slot = 0; slot < transport::FRAME_SLOTS; ++slot) {
			if (view.header().frames[slot].frame_id != frame_id) continue;
			for (std::uint32_t row = 0; row < transport::FRAME_HEIGHT; ++row)
				std::memcpy(command_shadows_[slot].data() + row * transport::FRAME_WIDTH,
				            source.data() + static_cast<std::size_t>(row) * source_pitch,
				            transport::FRAME_WIDTH);
			command_shadow_valid_[slot] = true;
			command_next_slot_ = (slot + 1U) % transport::FRAME_SLOTS;
			return;
		}
	}


private:
 friend class Adapter;
#ifdef DIABLO_MISTER_INPUT_TEST
 friend class InputAdapterTest;
#endif
	struct CommandSubmission {
		bool active = false;
		bool timed_out = false;
		bool wait_recorded = false;
		std::uint32_t slot = 0;
		std::uint32_t epoch = 0;
		std::uint64_t fence = 0;
		std::uint64_t frame_id = 0;
		std::uint64_t logic_tick = 0;
		std::uint64_t submitted_ns = 0;
		std::uint64_t deadline_ns = 0;
	};
	std::shared_ptr<std::array<std::uint8_t, transport::FRAME_PIXEL_BYTES>[]> command_shadows_ =
	    std::make_shared<std::array<std::uint8_t, transport::FRAME_PIXEL_BYTES>[]>(transport::FRAME_SLOTS);
	std::array<bool, transport::FRAME_SLOTS> command_shadow_valid_ {};
	std::uint32_t command_next_slot_ = 0;
	std::uint64_t command_attempt_fence_ = 1;
	CommandSubmission command_submission_ {};
	bool command_scene_faulted_ = false;
};
} // namespace diablo::mister::sdl
