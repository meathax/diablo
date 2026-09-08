// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <time.h>

namespace diablo::mister::sdl {
// Main-thread metrics and fixed-capacity trace owner. No transport lifetime or
// DDR access; Adapter measures its operations and reports their outcomes here.
class TransportProfiler {
public:
	enum class ProfileOutcome : std::size_t {
		RuntimeUnavailable,
		RecoveryDeferred,
		RecoveryFailed,
		InvalidSurface,
		CommandPublished,
		CommandRejected,
		FramePublished,
		PublishFailed,
		BackpressureDropped,
		Count,
	};
	static bool ProfileEnabled()
	{
		static const bool enabled = [] {
			const char *value = std::getenv("DIABLO_MISTER_PROFILE");
			return value != nullptr && (std::strcmp(value, "1") == 0
			                            || std::strcmp(value, "true") == 0);
		}();
		return enabled;
	}

	static const char *ProfileTracePath()
	{
		// This is intentionally separate from DIABLO_MISTER_PROFILE. A normal
		// profile run remains aggregate-only; an explicit path enables the bounded
		// per-presentation trace used for qualification and reconciliation.
		static const char *path = [] {
			const char *value = std::getenv("DIABLO_MISTER_PROFILE_TRACE");
			return value != nullptr && value[0] != '\0' ? value : nullptr;
		}();
		return path;
	}

	static std::uint64_t NowNs()
	{
		timespec now {};
		if (::clock_gettime(CLOCK_MONOTONIC, &now) != 0) return 0;
		return static_cast<std::uint64_t>(now.tv_sec) * 1'000'000'000ULL
		     + static_cast<std::uint64_t>(now.tv_nsec);
	}

	void RecordPublish(std::uint64_t start)
	{
		if (!ProfileEnabled() || start == 0) return;
		const std::uint64_t finish = NowNs();
		if (finish == 0 || finish < start) return;
		const std::uint64_t elapsed = finish - start;
		++profile_publish_attempts_;
		profile_publish_total_ns_ += elapsed;
		profile_publish_max_ns_ = std::max(profile_publish_max_ns_, elapsed);
	}

	void RecordFlush(std::uint64_t start)
	{
		if (!ProfileEnabled() || start == 0) return;
		const std::uint64_t finish = NowNs();
		if (finish == 0 || finish < start) return;
		const std::uint64_t elapsed = finish - start;
		++profile_flush_count_;
		profile_flush_total_ns_ += elapsed;
		profile_flush_max_ns_ = std::max(profile_flush_max_ns_, elapsed);
	}

	void RecordProfile(std::uint64_t start, bool published, bool saw_backpressure, ProfileOutcome outcome)
	{
		if (!ProfileEnabled()) return;
		const std::uint64_t finish = start == 0 ? 0 : NowNs();
		const bool timing_valid = start != 0 && finish != 0 && finish >= start;
		const std::uint64_t elapsed = timing_valid ? finish - start : 0;
		++profile_present_count_;
		if (published) ++profile_published_count_;
		if (saw_backpressure) ++profile_backpressure_count_;
		++profile_outcome_counts_[static_cast<std::size_t>(outcome)];
		if (timing_valid) {
			profile_total_ns_ += elapsed;
			profile_max_ns_ = std::max(profile_max_ns_, elapsed);
		} else {
			++profile_timing_invalid_count_;
		}
		RecordProfileTrace(start, finish, elapsed, timing_valid, published, saw_backpressure, outcome);
	}

	static const char *ProfileOutcomeName(ProfileOutcome outcome)
	{
		switch (outcome) {
		case ProfileOutcome::RuntimeUnavailable: return "runtime_unavailable";
		case ProfileOutcome::RecoveryDeferred: return "recovery_deferred";
		case ProfileOutcome::RecoveryFailed: return "recovery_failed";
		case ProfileOutcome::InvalidSurface: return "invalid_surface";
		case ProfileOutcome::CommandPublished: return "command_published";
		case ProfileOutcome::CommandRejected: return "command_rejected";
		case ProfileOutcome::FramePublished: return "frame_published";
		case ProfileOutcome::PublishFailed: return "publish_failed";
		case ProfileOutcome::BackpressureDropped: return "backpressure_dropped";
		default: return "unknown";
		}
	}

	void ResetProfile()
	{
		profile_present_count_ = 0;
		profile_published_count_ = 0;
		profile_backpressure_count_ = 0;
		profile_outcome_counts_.fill(0);
		profile_total_ns_ = 0;
		profile_max_ns_ = 0;
		profile_timing_invalid_count_ = 0;
		profile_publish_attempts_ = 0;
		profile_publish_total_ns_ = 0;
		profile_publish_max_ns_ = 0;
		profile_flush_count_ = 0;
		profile_flush_total_ns_ = 0;
		profile_flush_max_ns_ = 0;
		profile_trace_count_ = 0;
		profile_trace_total_ = 0;
		profile_trace_dropped_ = 0;
		profile_trace_write_failed_ = false;
		command_scene_attempts_ = 0;
		command_scene_no_slot_ = 0;
		command_scene_overflow_ = 0;
		command_scene_publish_failures_ = 0;
		command_scene_fence_failures_ = 0;
		command_scene_frame_failures_ = 0;
		command_scene_batches_ = 0;
		command_build_count_ = 0;
		command_build_total_ns_ = 0;
		command_build_max_ns_ = 0;
		command_wait_count_ = 0;
		command_wait_total_ns_ = 0;
		command_wait_max_ns_ = 0;
	}

	void RecordCommandBuild(std::uint64_t start, std::uint64_t finish)
	{
		if (!ProfileEnabled() || start == 0 || finish == 0 || finish < start) return;
		const std::uint64_t elapsed = finish - start;
		++command_build_count_;
		command_build_total_ns_ += elapsed;
		command_build_max_ns_ = std::max(command_build_max_ns_, elapsed);
	}

	void RecordProfileTrace(std::uint64_t start, std::uint64_t finish, std::uint64_t elapsed,
	                        bool timing_valid, bool published, bool saw_backpressure,
	                        ProfileOutcome outcome)
	{
		if (ProfileTracePath() == nullptr) return;
		const auto sequence = profile_trace_total_++;
		if (profile_trace_count_ == kProfileTraceCapacity) {
			++profile_trace_dropped_;
		} else {
			++profile_trace_count_;
		}
		profile_trace_[sequence % kProfileTraceCapacity] = ProfileTraceRecord {
			.sequence = sequence,
			.start_ns = start,
			.finish_ns = finish,
			.elapsed_ns = elapsed,
			.outcome = outcome,
			.published = published,
			.saw_backpressure = saw_backpressure,
			.timing_valid = timing_valid,
		};
	}

	void EmitProfile() const
	{
		if (!ProfileEnabled() || profile_present_count_ == 0) return;
		const auto timed_present_count = profile_present_count_ - profile_timing_invalid_count_;
		const auto average_us = timed_present_count == 0 ? 0 : profile_total_ns_ /
		                        timed_present_count / 1000U;
		const auto maximum_us = profile_max_ns_ / 1000U;
		const auto average_publish_us = profile_publish_attempts_ == 0
			? 0 : profile_publish_total_ns_ / profile_publish_attempts_ / 1000U;
		const auto maximum_publish_us = profile_publish_max_ns_ / 1000U;
		const auto average_flush_us = profile_flush_count_ == 0
			? 0 : profile_flush_total_ns_ / profile_flush_count_ / 1000U;
		const auto maximum_flush_us = profile_flush_max_ns_ / 1000U;
		const auto average_command_build_us = command_build_count_ == 0
			? 0 : command_build_total_ns_ / command_build_count_ / 1000U;
		const auto maximum_command_build_us = command_build_max_ns_ / 1000U;
		const auto average_command_wait_us = command_wait_count_ == 0
			? 0 : command_wait_total_ns_ / command_wait_count_ / 1000U;
		const auto maximum_command_wait_us = command_wait_max_ns_ / 1000U;
		std::fprintf(stderr,
		             "Diablo MiSTer profile: presents=%llu published=%llu "
		             "backpressure=%llu timing_invalid=%llu average_present_us=%llu max_present_us=%llu "
		             "publish_attempts=%llu average_publish_us=%llu max_publish_us=%llu "
		             "flushes=%llu average_flush_us=%llu max_flush_us=%llu "
		             "command_attempts=%llu command_batches=%llu command_no_slot=%llu "
			             "command_overflow=%llu command_publish_failures=%llu "
			             "command_fence_failures=%llu command_frame_failures=%llu\n",
		             static_cast<unsigned long long>(profile_present_count_),
		             static_cast<unsigned long long>(profile_published_count_),
		             static_cast<unsigned long long>(profile_backpressure_count_),
		             static_cast<unsigned long long>(profile_timing_invalid_count_),
		             static_cast<unsigned long long>(average_us),
		             static_cast<unsigned long long>(maximum_us),
		             static_cast<unsigned long long>(profile_publish_attempts_),
		             static_cast<unsigned long long>(average_publish_us),
		             static_cast<unsigned long long>(maximum_publish_us),
		             static_cast<unsigned long long>(profile_flush_count_),
		             static_cast<unsigned long long>(average_flush_us),
		             static_cast<unsigned long long>(maximum_flush_us),
		             static_cast<unsigned long long>(command_scene_attempts_),
		             static_cast<unsigned long long>(command_scene_batches_),
		             static_cast<unsigned long long>(command_scene_no_slot_),
		             static_cast<unsigned long long>(command_scene_overflow_),
			             static_cast<unsigned long long>(command_scene_publish_failures_),
			             static_cast<unsigned long long>(command_scene_fence_failures_),
		             static_cast<unsigned long long>(command_scene_frame_failures_));
		std::fprintf(stderr,
		             "Diablo MiSTer profile outcomes: runtime_unavailable=%llu recovery_deferred=%llu "
		             "recovery_failed=%llu invalid_surface=%llu command_published=%llu "
		             "command_rejected=%llu frame_published=%llu publish_failed=%llu "
		             "backpressure_dropped=%llu\n",
		             static_cast<unsigned long long>(profile_outcome_counts_[static_cast<std::size_t>(ProfileOutcome::RuntimeUnavailable)]),
		             static_cast<unsigned long long>(profile_outcome_counts_[static_cast<std::size_t>(ProfileOutcome::RecoveryDeferred)]),
		             static_cast<unsigned long long>(profile_outcome_counts_[static_cast<std::size_t>(ProfileOutcome::RecoveryFailed)]),
		             static_cast<unsigned long long>(profile_outcome_counts_[static_cast<std::size_t>(ProfileOutcome::InvalidSurface)]),
		             static_cast<unsigned long long>(profile_outcome_counts_[static_cast<std::size_t>(ProfileOutcome::CommandPublished)]),
		             static_cast<unsigned long long>(profile_outcome_counts_[static_cast<std::size_t>(ProfileOutcome::CommandRejected)]),
		             static_cast<unsigned long long>(profile_outcome_counts_[static_cast<std::size_t>(ProfileOutcome::FramePublished)]),
		             static_cast<unsigned long long>(profile_outcome_counts_[static_cast<std::size_t>(ProfileOutcome::PublishFailed)]),
		             static_cast<unsigned long long>(profile_outcome_counts_[static_cast<std::size_t>(ProfileOutcome::BackpressureDropped)]));
		std::fprintf(stderr,
		             "Diablo MiSTer command profile: build_count=%llu average_build_us=%llu max_build_us=%llu "
		             "wait_count=%llu average_wait_us=%llu max_wait_us=%llu\n",
		             static_cast<unsigned long long>(command_build_count_),
		             static_cast<unsigned long long>(average_command_build_us),
		             static_cast<unsigned long long>(maximum_command_build_us),
		             static_cast<unsigned long long>(command_wait_count_),
		             static_cast<unsigned long long>(average_command_wait_us),
			             static_cast<unsigned long long>(maximum_command_wait_us));
		if (ProfileTracePath() != nullptr)
			std::fprintf(stderr, "Diablo MiSTer profile trace write failed: %s\n",
			             profile_trace_write_failed_ ? "true" : "false");
	}

	[[nodiscard]] bool EmitProfileTrace()
	{
		const char *path = ProfileTracePath();
		if (path == nullptr) return true;
		// A trace is evidence input, not a rolling debug log. Refuse to replace
		// an existing path so two runs cannot silently destroy the first run's
		// provenance. Callers can provide a fresh run-specific path.
		std::FILE *trace = std::fopen(path, "wbx");
		if (trace == nullptr) {
			profile_trace_write_failed_ = true;
			std::fprintf(stderr, "Diablo MiSTer profile trace open failed: %s\n", path);
			return false;
		}
		bool write_ok = std::fprintf(trace,
		             "{\"schema\":\"diablo-presentation-trace-v1\",\"records\":%llu,\"dropped_records\":%llu,\"timing_invalid_records\":%llu}\n",
		             static_cast<unsigned long long>(profile_trace_count_),
		             static_cast<unsigned long long>(profile_trace_dropped_),
		             static_cast<unsigned long long>(profile_timing_invalid_count_));
		const auto first_sequence = profile_trace_total_ - profile_trace_count_;
		for (std::uint64_t sequence = first_sequence; sequence < profile_trace_total_; ++sequence) {
			const auto &record = profile_trace_[sequence % kProfileTraceCapacity];
			if (std::fprintf(trace,
			             "{\"sequence\":%llu,\"start_ns\":%llu,\"finish_ns\":%llu,\"elapsed_ns\":%llu,\"timing_valid\":%s,\"published\":%s,\"backpressure\":%s,\"outcome\":\"%s\"}\n",
			             static_cast<unsigned long long>(record.sequence),
			             static_cast<unsigned long long>(record.start_ns),
			             static_cast<unsigned long long>(record.finish_ns),
			             static_cast<unsigned long long>(record.elapsed_ns),
			             record.timing_valid ? "true" : "false",
			             record.published ? "true" : "false",
			             record.saw_backpressure ? "true" : "false",
			             ProfileOutcomeName(record.outcome)) < 0)
				write_ok = false;
		}
		if (std::fclose(trace) != 0)
			write_ok = false;
		if (!write_ok) {
			profile_trace_write_failed_ = true;
			// The path was opened exclusively, so removing a partial new file
			// cannot delete another run's evidence. A later run may retry with it.
			(void)std::remove(path);
			std::fprintf(stderr, "Diablo MiSTer profile trace write/close failed: %s\n", path);
			return false;
		}
		return true;
	}

private:
 friend class Adapter;
 friend class CommandFrameState;
#ifdef DIABLO_MISTER_INPUT_TEST
 friend class InputAdapterTest;
 friend class TransportProfileTest;
#endif
	struct ProfileTraceRecord {
		std::uint64_t sequence = 0;
		std::uint64_t start_ns = 0;
		std::uint64_t finish_ns = 0;
		std::uint64_t elapsed_ns = 0;
		ProfileOutcome outcome = ProfileOutcome::RuntimeUnavailable;
		bool published = false;
		bool saw_backpressure = false;
		bool timing_valid = false;
	};
	static constexpr std::size_t kProfileTraceCapacity = 4096;
	std::uint64_t profile_present_count_ = 0;
	std::uint64_t profile_published_count_ = 0;
	std::uint64_t profile_backpressure_count_ = 0;
	std::array<std::uint64_t, static_cast<std::size_t>(ProfileOutcome::Count)> profile_outcome_counts_ {};
	std::uint64_t profile_total_ns_ = 0;
	std::uint64_t profile_max_ns_ = 0;
	std::uint64_t profile_timing_invalid_count_ = 0;
	std::uint64_t profile_publish_attempts_ = 0;
	std::uint64_t profile_publish_total_ns_ = 0;
	std::uint64_t profile_publish_max_ns_ = 0;
	std::uint64_t profile_flush_count_ = 0;
	std::uint64_t profile_flush_total_ns_ = 0;
	std::uint64_t profile_flush_max_ns_ = 0;
	std::array<ProfileTraceRecord, kProfileTraceCapacity> profile_trace_ {};
	std::uint64_t profile_trace_count_ = 0;
	std::uint64_t profile_trace_total_ = 0;
	std::uint64_t profile_trace_dropped_ = 0;
	bool profile_trace_write_failed_ = false;
	std::uint64_t command_scene_attempts_ = 0;
	std::uint64_t command_scene_no_slot_ = 0;
	std::uint64_t command_scene_overflow_ = 0;
	std::uint64_t command_scene_publish_failures_ = 0;
	std::uint64_t command_scene_fence_failures_ = 0;
	std::uint64_t command_scene_frame_failures_ = 0;
	std::uint64_t command_scene_batches_ = 0;
	std::uint64_t command_build_count_ = 0;
	std::uint64_t command_build_total_ns_ = 0;
	std::uint64_t command_build_max_ns_ = 0;
	std::uint64_t command_wait_count_ = 0;
	std::uint64_t command_wait_total_ns_ = 0;
	std::uint64_t command_wait_max_ns_ = 0;
};
} // namespace diablo::mister::sdl
