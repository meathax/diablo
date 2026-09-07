#pragma once

#include "mister_command_scene.hpp"
#include "mister_command_transport.hpp"
#include "mister_transport_config.hpp"
#include "mister_transport_runtime.hpp"

#include <SDL.h>

#include <algorithm>
#include <atomic>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <optional>
#include <memory>
#include <span>
#include <time.h>
#include <utility>

namespace diablo::mister::sdl {

class Adapter {
public:
	using PcmFrame = std::array<std::int16_t, 2>;
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

	static Adapter &Instance()
	{
		static Adapter adapter;
		return adapter;
	}

	[[nodiscard]] bool Requested() const
	{
		return transport::ParseTransportRequest(std::getenv("DIABLO_MISTER_TRANSPORT"))
		    == transport::TransportRequest::Enabled;
	}

	[[nodiscard]] bool Initialize()
	{
		const auto request = transport::ParseTransportRequest(std::getenv("DIABLO_MISTER_TRANSPORT"));
		if (request == transport::TransportRequest::Invalid) {
			std::fprintf(stderr, "Diablo MiSTer transport configuration failed: %s\n",
			             transport::TransportRequestError(request));
			return false;
		}
		if (request != transport::TransportRequest::Enabled) return false;
		// The target entry point performs early admission before SDL starts. Keep
		// dx_init's existing call safe and idempotent rather than reopening the
		// mapping/resetting state after a successful admission.
		if (Runtime()) return true;
		auto opened = transport::TransportRuntime::Open();
		if (!opened.has_value()) {
			std::fprintf(stderr, "Diablo MiSTer transport open failed: error=%u\n",
			             static_cast<unsigned>(opened.error()));
			return false;
		}
		RequestAudioReset();
		runtime_transition_generation_.store(0, std::memory_order_release);
		runtime_.store(std::make_shared<transport::TransportRuntime>(std::move(*opened)),
		               std::memory_order_release);
		startup_waited_ = false;
		pcm_publish_notices_ = 0;
		pcm_drop_notices_ = 0;
		pcm_published_frames_ = 0;
		pcm_dropped_frames_ = 0;
		pcm_health_valid_ = false;
		pcm_health_poll_count_ = 0;
		ResetProfile();
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
		ResetCommandSceneState();
		pcm_health_valid_ = false;
		ResetInputState();
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
		return true;
	}

	void Shutdown()
	{
		EmitProfile();
		(void)EmitProfileTrace();
		// Audio callbacks take their own shared runtime reference. Releasing the
		// adapter's reference first prevents any new callback from mapping/writing
		// the old epoch while an in-flight callback keeps its mapping alive.
		(void)runtime_.exchange(std::shared_ptr<transport::TransportRuntime> {},
		                        std::memory_order_acq_rel);
		startup_waited_ = false;
		RequestAudioReset();
		ResetCommandSceneState();
		ResetInputState();
	}

	[[nodiscard]] bool Active() const { return static_cast<bool>(Runtime()); }

	[[nodiscard]] bool CpuPacingEnabled() const
	{
		const char *value = std::getenv("DIABLO_MISTER_NO_CPU_PACING");
		return value == nullptr || (std::strcmp(value, "0") == 0
		                            || std::strcmp(value, "false") == 0);
	}

	// Copies the engine's native indexed surface into one ABI frame slot. The
	// caller remains the pacing authority; a short bounded wait handles an FPGA
	// consumer that is still retiring the previous three slots.
	[[nodiscard]] bool Present(SDL_Surface *surface, std::uint64_t logic_tick)
	{
		const std::uint64_t profile_start = ProfileEnabled() ? NowNs() : 0;
		auto runtime = Runtime();
		if (!runtime) {
			RecordProfile(profile_start, false, false, ProfileOutcome::RuntimeUnavailable);
			return false;
		}
		const auto fpga_state = std::atomic_ref<std::uint32_t>(
			runtime->session().view().header().fpga_state).load(std::memory_order_acquire);
		if (fpga_state == static_cast<std::uint32_t>(transport::ComponentState::Fault)) {
			if (!BeginRuntimeTransition()) {
				// Gate recovery until every callback that entered its read-side
				// critical section has exited. This is non-blocking on Present.
				RecordProfile(profile_start, false, false, ProfileOutcome::RecoveryDeferred);
				return false;
			}
			const bool recovered = runtime->RecoverAfterFpgaFault();
			EndRuntimeTransition();
			if (!recovered) {
				RecordProfile(profile_start, false, false, ProfileOutcome::RecoveryFailed);
				return false;
			}
			std::fputs("Diablo MiSTer transport recovered after FPGA reset\n", stderr);
			startup_waited_ = false;
			RequestAudioReset();
			RecoverInputAfterDiscontinuity();
			ResetCommandSceneState();
		}
		if (!startup_waited_) {
			startup_waited_ = true;
			if (!runtime->WaitForFpgaReady(1000))
				std::fputs("Diablo MiSTer transport FPGA startup wait expired\n", stderr);
		}
		PumpInput();
		ObservePcmHealth(*runtime);
		if (surface == nullptr || surface->pixels == nullptr || surface->format == nullptr
		    || surface->format->BitsPerPixel != 8 || surface->format->palette == nullptr
		    || surface->format->palette->ncolors != 256
		    || surface->w < static_cast<int>(transport::FRAME_WIDTH)
		    || surface->h < static_cast<int>(transport::FRAME_HEIGHT)
			|| surface->pitch < static_cast<int>(transport::FRAME_WIDTH)) {
			std::fprintf(stderr, "Diablo MiSTer transport rejected indexed surface\n");
			FlushProfiled();
			RecordProfile(profile_start, false, false, ProfileOutcome::InvalidSurface);
			return false;
		}

		std::array<std::uint8_t, transport::PALETTE_BYTES> palette {};
		for (std::size_t index = 0; index < 256; ++index) {
			const SDL_Color color = surface->format->palette->colors[index];
			palette[index * 3 + 0] = color.r;
			palette[index * 3 + 1] = color.g;
			palette[index * 3 + 2] = color.b;
		}
		const auto *pixels = static_cast<const std::uint8_t *>(surface->pixels);
		const std::span<const std::uint8_t> source(
		    pixels, static_cast<std::size_t>(surface->pitch) * surface->h);
		if (CommandSceneEnabled()) {
			auto command_result = TryPresentCommand(source, static_cast<std::size_t>(surface->pitch),
			                                      palette, logic_tick);
			if (command_result.has_value()) {
				FlushProfiled();
				RecordProfile(profile_start, *command_result, false,
				              *command_result ? ProfileOutcome::CommandPublished : ProfileOutcome::CommandRejected);
				return *command_result;
			}
		}
		// Never turn a full three-slot pipeline into a long CPU stall. A single
		// short retry absorbs an immediate vblank handoff; if the FPGA is still
		// retiring the previous frame, let SDL pacing run and retry the latest
		// surface on the next presentation.
		bool saw_backpressure = false;
		for (unsigned retry = 0; retry < 2; ++retry) {
			const std::uint64_t publish_start = ProfileEnabled() ? NowNs() : 0;
			auto published = runtime->session().PublishIndexedFrame(
				source, static_cast<std::size_t>(surface->pitch), palette, logic_tick);
			RecordPublish(publish_start);
			if (published.has_value()) {
				if (CommandSceneEnabled())
					RememberFullFrame(*published, source, static_cast<std::size_t>(surface->pitch));
				FlushProfiled();
				RecordProfile(profile_start, true, saw_backpressure, ProfileOutcome::FramePublished);
				return true;
			}
			if (published.error() != transport::PublishError::Backpressure) {
				std::fprintf(stderr, "Diablo MiSTer transport frame publish failed: error=%u\n",
				             static_cast<unsigned>(published.error()));
				FlushProfiled();
				RecordProfile(profile_start, false, saw_backpressure, ProfileOutcome::PublishFailed);
				return false;
			}
			saw_backpressure = true;
			SDL_Delay(1);
		}
		static std::uint32_t backpressure_drops = 0;
		if ((++backpressure_drops & 63U) == 1U)
			std::fputs("Diablo MiSTer transport frame backpressure; using SDL pacing\n", stderr);
		FlushProfiled();
		RecordProfile(profile_start, false, saw_backpressure, ProfileOutcome::BackpressureDropped);
		return false;
	}

	// Aulib's SDL callback supplies interleaved little-endian S16 stereo at the
	// efficient 22.05 kHz ARM mix rate. Resample those frames to the FPGA's
	// fixed 48 kHz ring without waiting in the callback or allocating.
	[[nodiscard]] bool PublishPcmBytes(const std::uint8_t *bytes, std::size_t byte_count)
	{
		if (bytes == nullptr || byte_count < 4 || (byte_count & 3U) != 0)
			return false;
		if (!BeginAudioCallback()) return false;
		struct CallbackFinished {
			std::atomic<std::uint32_t> &count;
			~CallbackFinished() { (void)count.fetch_sub(1U, std::memory_order_release); }
		} callback_finished {audio_callbacks_inflight_};
		auto runtime = Runtime();
		if (!runtime) return false;
		if (std::atomic_ref<std::uint32_t>(runtime->session().view().header().fpga_state)
		        .load(std::memory_order_acquire)
		    == static_cast<std::uint32_t>(transport::ComponentState::Fault))
			return false;
		const std::uint32_t audio_generation = audio_reset_generation_.load(std::memory_order_acquire);
		if (resample_generation_ != audio_generation) {
			resample_position_ = 0;
			resample_have_previous_ = false;
			resample_generation_ = audio_generation;
		}
		const std::size_t source_frames = byte_count / 4U;
		if (source_frames > kMaxSourceFrames) return false;
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
			if (output_frames >= kMaxOutputFrames) return false;
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
		if (output_frames == 0) return true;

		const std::uint32_t epoch = runtime->session().epoch();
		const auto pcm_bytes = std::span<const std::byte>(
			resample_output_.data(), output_frames * 4U);
		if (!runtime->session().view().ArmPublishPcmBytesFast(pcm_bytes, epoch)) {
			pcm_dropped_frames_.fetch_add(output_frames, std::memory_order_relaxed);
			if ((++pcm_drop_notices_ & 63U) == 1U)
				std::fputs("Diablo MiSTer transport PCM backpressure; dropping callback chunk\n", stderr);
			return false;
		}
		pcm_published_frames_.fetch_add(output_frames, std::memory_order_relaxed);
		const std::uint32_t published_callbacks =
			pcm_publish_notices_.fetch_add(1U, std::memory_order_relaxed);
		if (AudioTraceEnabled() && (published_callbacks & 63U) == 0U)
			std::fprintf(stderr,
		             "Diablo MiSTer PCM callback: input_bytes=%zu output_frames=%zu epoch=0x%08x\n",
			             byte_count, output_frames, epoch);
		(void)runtime->Flush();
		return true;
	}

private:
#ifdef DIABLO_MISTER_INPUT_TEST
	friend class InputAdapterTest;
	friend class TransportProfileTest;
#endif
	[[nodiscard]] std::shared_ptr<transport::TransportRuntime> Runtime() const
	{
		return runtime_.load(std::memory_order_acquire);
	}

	void ResetCommandSceneState()
	{
		command_shadow_valid_.fill(false);
		command_next_slot_ = 0;
		command_attempt_fence_ = 1;
		command_submission_ = {};
		command_scene_faulted_ = false;
	}

	void RequestAudioReset()
	{
		(void)audio_reset_generation_.fetch_add(1U, std::memory_order_release);
	}

	void ObservePcmHealth(const transport::TransportRuntime &runtime)
	{
		if ((++pcm_health_poll_count_ & 63U) != 0U) return;
		auto health = runtime.session().ReadPcmHealth();
		if (!health.has_value()) return;
		if (pcm_health_valid_
		    && (health->underrun_count != pcm_health_.underrun_count
		        || health->resync_count != pcm_health_.resync_count)) {
			std::fprintf(stderr,
			             "Diablo MiSTer PCM health changed: queued=%u producer=%u consumer=%u "
			             "underrun=%u resync=%u callbacks=%u drops=%u frames=%llu dropped_frames=%llu\n",
			             health->queued_frames, health->producer_sequence, health->consumer_sequence,
			             health->underrun_count, health->resync_count,
			             pcm_publish_notices_.load(std::memory_order_relaxed),
			             pcm_drop_notices_.load(std::memory_order_relaxed),
			             static_cast<unsigned long long>(
			                 pcm_published_frames_.load(std::memory_order_relaxed)),
			             static_cast<unsigned long long>(
			                 pcm_dropped_frames_.load(std::memory_order_relaxed)));
		}
		pcm_health_ = *health;
		pcm_health_valid_ = true;
	}

	// A callback captures an even generation before incrementing its reader
	// count, then confirms it still owns that generation. A recovery first makes
	// the generation odd. It therefore cannot race a callback's session or
	// resampler access, even in the narrow interval between the initial load and
	// increment of the reader count.
	[[nodiscard]] bool BeginAudioCallback()
	{
		const std::uint32_t generation = runtime_transition_generation_.load(std::memory_order_acquire);
		if ((generation & 1U) != 0) return false;
		audio_callbacks_inflight_.fetch_add(1U, std::memory_order_acq_rel);
		if (runtime_transition_generation_.load(std::memory_order_acquire) == generation)
			return true;
		(void)audio_callbacks_inflight_.fetch_sub(1U, std::memory_order_release);
		return false;
	}

	[[nodiscard]] bool BeginRuntimeTransition()
	{
		std::uint32_t generation = runtime_transition_generation_.load(std::memory_order_acquire);
		while ((generation & 1U) == 0) {
			if (runtime_transition_generation_.compare_exchange_weak(
			        generation, generation + 1U, std::memory_order_acq_rel,
			        std::memory_order_acquire)) {
				if (audio_callbacks_inflight_.load(std::memory_order_acquire) == 0) return true;
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

	// The command path is deliberately opt-in while the full-game scene mix is
	// being characterised. It claims a free frame slot, emits only changed
	// horizontal runs, waits for the FPGA fence, then publishes the frame state.
	// If the scene cannot fit in 2,048 records, it returns nullopt and the caller
	// immediately uses the existing full-copy publisher.
	static bool CommandSceneEnabled()
	{
		static const bool enabled = [] {
			const char *value = std::getenv("DIABLO_MISTER_COMMAND_SCENE");
			return value != nullptr && (std::strcmp(value, "1") == 0
			                            || std::strcmp(value, "true") == 0);
		}();
		return enabled;
	}

	static unsigned CommandWaitMs()
	{
		static const unsigned timeout = [] {
			const char *value = std::getenv("DIABLO_MISTER_COMMAND_WAIT_MS");
			if (value == nullptr || *value == '\0') return 25U;
			char *end = nullptr;
			const auto parsed = std::strtoul(value, &end, 10);
			if (end == value || *end != '\0') return 25U;
			return static_cast<unsigned>(std::clamp<unsigned long>(parsed, 1UL, 1000UL));
		}();
		return timeout;
	}

	struct CommandSubmission {
		bool active = false;
		bool timed_out = false;
		std::uint32_t slot = 0;
		std::uint32_t epoch = 0;
		std::uint64_t fence = 0;
		std::uint64_t frame_id = 0;
		std::uint64_t logic_tick = 0;
		std::uint64_t submitted_ns = 0;
		std::uint64_t deadline_ns = 0;
	};

	void FaultCommandSubmission(transport::AbiView view)
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
		++command_scene_fence_failures_;
	}

	void ReconcileCommandSubmission()
	{
		auto runtime = Runtime();
		if (!command_submission_.active || !runtime) return;
		auto view = runtime->session().view();
		if (runtime->session().epoch() != command_submission_.epoch) {
			// RebindEpoch invalidates the TransportSession caches and resets every
			// ABI slot. The adapter's command shadows must be invalidated too or a
			// post-reset changed-run command could skip pixels that are now zero.
			ResetCommandSceneState();
			return;
		}
		std::atomic_ref<std::uint64_t> completed(view.header().last_completed_fence);
		if (completed.load(std::memory_order_acquire) == command_submission_.fence) {
			if (!command_submission_.timed_out) {
				if (view.ArmPublishFrameFast(command_submission_.slot, command_submission_.epoch,
				                             command_submission_.frame_id, command_submission_.logic_tick,
				                             command_submission_.fence, 0, transport::FRAME_CHECKSUM_ABSENT)) {
					command_shadow_valid_[command_submission_.slot] = true;
					++command_scene_batches_;
				} else {
					FaultCommandSubmission(view);
				}
			}
			if (ProfileEnabled() && command_submission_.submitted_ns != 0) {
				const std::uint64_t elapsed = NowNs() - command_submission_.submitted_ns;
				++command_wait_count_;
				command_wait_total_ns_ += elapsed;
				command_wait_max_ns_ = std::max(command_wait_max_ns_, elapsed);
			}
			command_submission_.active = false;
			return;
		}
		if (!command_submission_.timed_out && NowNs() >= command_submission_.deadline_ns) {
			FaultCommandSubmission(view);
			if (ProfileEnabled() && command_submission_.submitted_ns != 0) {
				const std::uint64_t elapsed = NowNs() - command_submission_.submitted_ns;
				++command_wait_count_;
				command_wait_total_ns_ += elapsed;
				command_wait_max_ns_ = std::max(command_wait_max_ns_, elapsed);
			}
		}
	}

	[[nodiscard]] std::optional<bool> TryPresentCommand(
	    std::span<const std::uint8_t> source, std::size_t source_pitch,
	    std::span<const std::uint8_t> palette, std::uint64_t logic_tick)
	{
		auto runtime = Runtime();
		if (!runtime) return std::nullopt;
		ReconcileCommandSubmission();
		if (command_submission_.active || command_scene_faulted_) return std::nullopt;
		++command_scene_attempts_;
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
			++command_scene_no_slot_;
			return std::nullopt;
		}

		command::Buffer commands;
		const std::uint64_t command_build_start = ProfileEnabled() ? NowNs() : 0;
		const auto shadow = std::span<const std::uint8_t>(
			command_shadows_[slot].data(), transport::FRAME_PIXEL_BYTES);
		const std::uint64_t fence = command_attempt_fence_ == 0 ? 1 : command_attempt_fence_;
		command_attempt_fence_ = fence + 1U;
		if (command_attempt_fence_ == 0) command_attempt_fence_ = 1;
		if (!command::BuildChangedRuns(commands, source, source_pitch, shadow, slot)) {
			++command_scene_overflow_;
			(void)view.ArmAbortFrameFast(slot, epoch);
			return std::nullopt;
		}
		if (!commands.End(fence)) {
			++command_scene_overflow_;
			(void)view.ArmAbortFrameFast(slot, epoch);
			return std::nullopt;
		}
		if (ProfileEnabled() && command_build_start != 0) {
			const std::uint64_t elapsed = NowNs() - command_build_start;
			++command_build_count_;
			command_build_total_ns_ += elapsed;
			command_build_max_ns_ = std::max(command_build_max_ns_, elapsed);
		}

		// The command path writes this slot's palette here and its pixels through
		// the FPGA. Invalidate TransportSession's full/dirty-copy caches before
		// either write is visible so a later fallback cannot skip stale bytes.
		if (!runtime->session().InvalidateSlotContentCache(slot)) {
			++command_scene_publish_failures_;
			(void)view.ArmAbortFrameFast(slot, epoch);
			return std::nullopt;
		}
		const auto &descriptor = view.header().frames[slot];
		std::memcpy(view.memory().data() + descriptor.palette_offset,
		            palette.data(), transport::PALETTE_BYTES);
		command::Publisher publisher(view, epoch);
		const auto published = publisher.Publish(commands.records(), {});
		if (!published.has_value()) {
			++command_scene_publish_failures_;
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
			.submitted_ns = NowNs(),
			.deadline_ns = NowNs() + static_cast<std::uint64_t>(CommandWaitMs()) * 1'000'000U,
		};
		if (!runtime->Flush()) {
			FaultCommandSubmission(view);
			return std::nullopt;
		}
		// Fence completion is serviced by future Present calls. Returning nullopt
		// lets the established full-frame producer use another free slot instead
		// of blocking the engine thread for the entire recovery interval.
		return std::nullopt;
	}

	void RememberFullFrame(std::uint64_t frame_id, std::span<const std::uint8_t> source,
	                       std::size_t source_pitch)
	{
		auto runtime = Runtime();
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

	static bool AudioTraceEnabled()
	{
		static const bool enabled = [] {
			const char *value = std::getenv("DIABLO_MISTER_AUDIO_TRACE");
			return value != nullptr && (std::strcmp(value, "1") == 0
			                            || std::strcmp(value, "true") == 0);
		}();
		return enabled;
	}

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

	void FlushProfiled()
	{
		auto runtime = Runtime();
		if (!runtime) return;
		const std::uint64_t start = ProfileEnabled() ? NowNs() : 0;
		(void)runtime->Flush();
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

	static constexpr std::array<SDL_Scancode, 16> kJoystickScancodes = {
		SDL_SCANCODE_RIGHT, SDL_SCANCODE_LEFT, SDL_SCANCODE_DOWN, SDL_SCANCODE_UP,
		SDL_SCANCODE_LALT, SDL_SCANCODE_LCTRL, SDL_SCANCODE_ESCAPE, SDL_SCANCODE_RETURN,
		SDL_SCANCODE_LSHIFT, SDL_SCANCODE_SPACE, SDL_SCANCODE_TAB, SDL_SCANCODE_BACKSPACE,
		SDL_SCANCODE_PAGEUP, SDL_SCANCODE_PAGEDOWN, SDL_SCANCODE_HOME, SDL_SCANCODE_END,
	};

	static SDL_Scancode Ps2Scancode(std::uint32_t code)
	{
		const bool extended = (code & 0x100U) != 0;
		const std::uint8_t scan = static_cast<std::uint8_t>(code & 0xffU);
		if (extended) {
			switch (scan) {
			case 0x11: return SDL_SCANCODE_RALT;
			case 0x14: return SDL_SCANCODE_RCTRL;
			case 0x4a: return SDL_SCANCODE_KP_DIVIDE;
			case 0x5a: return SDL_SCANCODE_KP_ENTER;
			case 0x69: return SDL_SCANCODE_END;
			case 0x6b: return SDL_SCANCODE_LEFT;
			case 0x6c: return SDL_SCANCODE_HOME;
			case 0x70: return SDL_SCANCODE_INSERT;
			case 0x71: return SDL_SCANCODE_DELETE;
			case 0x72: return SDL_SCANCODE_DOWN;
			case 0x74: return SDL_SCANCODE_RIGHT;
			case 0x75: return SDL_SCANCODE_UP;
			case 0x7a: return SDL_SCANCODE_PAGEDOWN;
			case 0x7d: return SDL_SCANCODE_PAGEUP;
			default: return SDL_SCANCODE_UNKNOWN;
			}
		}
		switch (scan) {
		case 0x05: return SDL_SCANCODE_F1;
		case 0x06: return SDL_SCANCODE_F2;
		case 0x04: return SDL_SCANCODE_F3;
		case 0x0c: return SDL_SCANCODE_F4;
		case 0x03: return SDL_SCANCODE_F5;
		case 0x0b: return SDL_SCANCODE_F6;
		case 0x83: return SDL_SCANCODE_F7;
		case 0x0a: return SDL_SCANCODE_F8;
		case 0x01: return SDL_SCANCODE_F9;
		case 0x09: return SDL_SCANCODE_F10;
		case 0x78: return SDL_SCANCODE_F11;
		case 0x07: return SDL_SCANCODE_F12;
		case 0x76: return SDL_SCANCODE_ESCAPE;
		case 0x0d: return SDL_SCANCODE_TAB;
		case 0x58: return SDL_SCANCODE_CAPSLOCK;
		case 0x12: return SDL_SCANCODE_LSHIFT;
		case 0x59: return SDL_SCANCODE_RSHIFT;
		case 0x14: return SDL_SCANCODE_LCTRL;
		case 0x11: return SDL_SCANCODE_LALT;
		case 0x66: return SDL_SCANCODE_BACKSPACE;
		case 0x5a: return SDL_SCANCODE_RETURN;
		case 0x29: return SDL_SCANCODE_SPACE;
		case 0x45: return SDL_SCANCODE_0;
		case 0x16: return SDL_SCANCODE_1;
		case 0x1e: return SDL_SCANCODE_2;
		case 0x26: return SDL_SCANCODE_3;
		case 0x25: return SDL_SCANCODE_4;
		case 0x2e: return SDL_SCANCODE_5;
		case 0x36: return SDL_SCANCODE_6;
		case 0x3d: return SDL_SCANCODE_7;
		case 0x3e: return SDL_SCANCODE_8;
		case 0x46: return SDL_SCANCODE_9;
		case 0x1c: return SDL_SCANCODE_A;
		case 0x32: return SDL_SCANCODE_B;
		case 0x21: return SDL_SCANCODE_C;
		case 0x23: return SDL_SCANCODE_D;
		case 0x24: return SDL_SCANCODE_E;
		case 0x2b: return SDL_SCANCODE_F;
		case 0x34: return SDL_SCANCODE_G;
		case 0x33: return SDL_SCANCODE_H;
		case 0x43: return SDL_SCANCODE_I;
		case 0x3b: return SDL_SCANCODE_J;
		case 0x42: return SDL_SCANCODE_K;
		case 0x4b: return SDL_SCANCODE_L;
		case 0x3a: return SDL_SCANCODE_M;
		case 0x31: return SDL_SCANCODE_N;
		case 0x44: return SDL_SCANCODE_O;
		case 0x4d: return SDL_SCANCODE_P;
		case 0x15: return SDL_SCANCODE_Q;
		case 0x2d: return SDL_SCANCODE_R;
		case 0x1b: return SDL_SCANCODE_S;
		case 0x2c: return SDL_SCANCODE_T;
		case 0x3c: return SDL_SCANCODE_U;
		case 0x2a: return SDL_SCANCODE_V;
		case 0x1d: return SDL_SCANCODE_W;
		case 0x22: return SDL_SCANCODE_X;
		case 0x35: return SDL_SCANCODE_Y;
		case 0x1a: return SDL_SCANCODE_Z;
		case 0x0e: return SDL_SCANCODE_GRAVE;
		case 0x4e: return SDL_SCANCODE_MINUS;
		case 0x55: return SDL_SCANCODE_EQUALS;
		case 0x54: return SDL_SCANCODE_LEFTBRACKET;
		case 0x5b: return SDL_SCANCODE_RIGHTBRACKET;
		case 0x5d: return SDL_SCANCODE_BACKSLASH;
		case 0x4c: return SDL_SCANCODE_SEMICOLON;
		case 0x52: return SDL_SCANCODE_APOSTROPHE;
		case 0x41: return SDL_SCANCODE_COMMA;
		case 0x49: return SDL_SCANCODE_PERIOD;
		case 0x4a: return SDL_SCANCODE_SLASH;
		default: return SDL_SCANCODE_UNKNOWN;
		}
	}

	// SDL_PushEvent returns 1 for a queued event, 0 when an event filter drops
	// it, and -1 when the queue cannot accept it. A filtered/failed event has not
	// reached the game, so it must not advance delivered input state.
	enum class EventPushResult : std::uint8_t { Queued, Filtered, Failed };

	[[nodiscard]] EventPushResult PushEvent(SDL_Event event)
	{
		const int result = SDL_PushEvent(&event);
		if (result > 0) return EventPushResult::Queued;
		if (result == 0) {
			if ((++input_push_filtered_ & 63U) == 1U)
				std::fputs("Diablo MiSTer transport SDL input event filtered\n", stderr);
			return EventPushResult::Filtered;
		}
		if ((++input_push_drops_ & 63U) == 1U)
			std::fputs("Diablo MiSTer transport SDL input queue full\n", stderr);
		return EventPushResult::Failed;
	}

	[[nodiscard]] static std::optional<std::size_t> KeyIndex(SDL_Scancode scancode)
	{
		const int value = static_cast<int>(scancode);
		if (scancode == SDL_SCANCODE_UNKNOWN || value < 0 || value >= SDL_NUM_SCANCODES)
			return std::nullopt;
		return static_cast<std::size_t>(value);
	}

	[[nodiscard]] static std::uint32_t MouseButtonMask(std::uint32_t ps2_buttons)
	{
		std::uint32_t mask = 0;
		if ((ps2_buttons & 0x1U) != 0) mask |= SDL_BUTTON_LMASK;
		if ((ps2_buttons & 0x2U) != 0) mask |= SDL_BUTTON_RMASK;
		if ((ps2_buttons & 0x4U) != 0) mask |= SDL_BUTTON_MMASK;
		return mask;
	}

	[[nodiscard]] bool JoystickWantsScancode(SDL_Scancode scancode) const
	{
		for (std::size_t index = 0; index < kJoystickScancodes.size(); ++index) {
			const std::uint32_t bit = 1U << index;
			if (kJoystickScancodes[index] == scancode
			    && (joystick_desired_mask_ & bit) != 0
			    && (joystick_repress_mask_ & bit) == 0)
				return true;
		}
		return false;
	}

	[[nodiscard]] bool KeyWanted(SDL_Scancode scancode) const
	{
		if (!requested_focus_) return false;
		const auto index = KeyIndex(scancode);
		if (!index.has_value()) return false;
		return (keyboard_desired_[*index] && !keyboard_repress_[*index])
		    || JoystickWantsScancode(scancode);
	}

	[[nodiscard]] bool PhysicalKeyWanted(SDL_Scancode scancode) const
	{
		if (!requested_focus_) return false;
		const auto index = KeyIndex(scancode);
		return index.has_value() && keyboard_desired_[*index] && !keyboard_repress_[*index];
	}

	[[nodiscard]] SDL_Keymod ModifierMask() const
	{
		SDL_Keymod modifiers = KMOD_NONE;
		if (PhysicalKeyWanted(SDL_SCANCODE_LSHIFT)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_LSHIFT);
		if (PhysicalKeyWanted(SDL_SCANCODE_RSHIFT)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_RSHIFT);
		if (PhysicalKeyWanted(SDL_SCANCODE_LCTRL)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_LCTRL);
		if (PhysicalKeyWanted(SDL_SCANCODE_RCTRL)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_RCTRL);
		if (PhysicalKeyWanted(SDL_SCANCODE_LALT)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_LALT);
		if (PhysicalKeyWanted(SDL_SCANCODE_RALT)) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_RALT);
		if (caps_lock_) modifiers = static_cast<SDL_Keymod>(modifiers | KMOD_CAPS);
		return modifiers;
	}

	[[nodiscard]] EventPushResult PushKey(SDL_Scancode scancode, bool pressed)
	{
		SDL_Event event {};
		event.type = pressed ? SDL_KEYDOWN : SDL_KEYUP;
		event.key.state = pressed ? SDL_PRESSED : SDL_RELEASED;
		event.key.repeat = 0;
		event.key.keysym.scancode = scancode;
		event.key.keysym.sym = SDL_GetKeyFromScancode(scancode);
		event.key.keysym.mod = ModifierMask();
		return PushEvent(event);
	}

	[[nodiscard]] static std::optional<char> TextCharacter(SDL_Scancode scancode, SDL_Keymod modifiers)
	{
		if ((modifiers & (KMOD_CTRL | KMOD_ALT | KMOD_GUI)) != 0) return std::nullopt;
		const bool shifted = (modifiers & KMOD_SHIFT) != 0;
		const bool uppercase = shifted != ((modifiers & KMOD_CAPS) != 0);
		if (scancode >= SDL_SCANCODE_A && scancode <= SDL_SCANCODE_Z) {
			const char base = static_cast<char>('a' + (static_cast<int>(scancode) - static_cast<int>(SDL_SCANCODE_A)));
			return uppercase ? static_cast<char>(base - 'a' + 'A') : base;
		}
		static constexpr std::array<char, 10> digits = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'};
		static constexpr std::array<char, 10> shifted_digits = {')', '!', '@', '#', '$', '%', '^', '&', '*', '('};
		if (scancode >= SDL_SCANCODE_0 && scancode <= SDL_SCANCODE_9) {
			const auto index = static_cast<std::size_t>(static_cast<int>(scancode) - static_cast<int>(SDL_SCANCODE_0));
			return shifted ? shifted_digits[index] : digits[index];
		}
		switch (scancode) {
		case SDL_SCANCODE_SPACE: return ' ';
		case SDL_SCANCODE_MINUS: return shifted ? '_' : '-';
		case SDL_SCANCODE_EQUALS: return shifted ? '+' : '=';
		case SDL_SCANCODE_LEFTBRACKET: return shifted ? '{' : '[';
		case SDL_SCANCODE_RIGHTBRACKET: return shifted ? '}' : ']';
		case SDL_SCANCODE_BACKSLASH: return shifted ? '|' : '\\';
		case SDL_SCANCODE_SEMICOLON: return shifted ? ':' : ';';
		case SDL_SCANCODE_APOSTROPHE: return shifted ? '"' : '\'';
		case SDL_SCANCODE_GRAVE: return shifted ? '~' : '`';
		case SDL_SCANCODE_COMMA: return shifted ? '<' : ',';
		case SDL_SCANCODE_PERIOD: return shifted ? '>' : '.';
		case SDL_SCANCODE_SLASH: return shifted ? '?' : '/';
		default: return std::nullopt;
		}
	}

	[[nodiscard]] bool PushText(SDL_Scancode scancode)
	{
		// A text event is only meaningful while the gameplay window owns focus
		// and SDL text input is active. Treat an inactive/non-character key as
		// consumed so it does not remain pending forever; retain a failed or
		// filtered event for the next bounded reconciliation pass.
		if (!requested_focus_ || !delivered_focus_ || SDL_IsTextInputActive() != SDL_TRUE) return true;
		const auto character = TextCharacter(scancode, ModifierMask());
		if (!character.has_value()) return true;
		SDL_Event event {};
		event.type = SDL_TEXTINPUT;
		event.text.text[0] = *character;
		event.text.text[1] = '\0';
		return PushEvent(event) == EventPushResult::Queued;
	}

	[[nodiscard]] bool AnyDeliveredInput() const
	{
		return std::any_of(keyboard_delivered_.begin(), keyboard_delivered_.end(), [](bool value) { return value; })
		    || mouse_delivered_buttons_ != 0;
	}

	void ReconcileInputState()
	{
		constexpr std::size_t kMaximumReconciledEvents = 32;
		std::size_t budget = kMaximumReconciledEvents;
		if (requested_focus_ != delivered_focus_ && budget != 0) {
			SDL_Event event {};
			event.type = SDL_WINDOWEVENT;
			event.window.event = requested_focus_ ? SDL_WINDOWEVENT_FOCUS_GAINED : SDL_WINDOWEVENT_FOCUS_LOST;
			if (PushEvent(event) == EventPushResult::Queued)
				delivered_focus_ = requested_focus_;
			--budget;
		}

		const bool deliver_gameplay = requested_focus_ && delivered_focus_;
		for (std::size_t index = 0; index < keyboard_delivered_.size() && budget != 0; ++index) {
			const auto scancode = static_cast<SDL_Scancode>(index);
			const bool target = deliver_gameplay && KeyWanted(scancode);
			if (keyboard_delivered_[index] == target) continue;
			if (PushKey(scancode, target) != EventPushResult::Queued) break;
			keyboard_delivered_[index] = target;
			--budget;
		}

		// Text input is a second SDL event and can be filtered or rejected even
		// after its keydown was accepted. Keep one pending bit per physical key
		// so a later reconciliation can deliver it without duplicating text.
		for (std::size_t index = 0; index < text_pending_.size() && budget != 0; ++index) {
			if (!text_pending_[index]) continue;
			const auto scancode = static_cast<SDL_Scancode>(index);
			if (!keyboard_desired_[index]) {
				text_pending_[index] = false;
				continue;
			}
			if (!keyboard_delivered_[index] || !deliver_gameplay) continue;
			if (!PushText(scancode)) break;
			text_pending_[index] = false;
			--budget;
		}

		static constexpr std::array<std::uint8_t, 3> mouse_buttons = {
			SDL_BUTTON_LEFT, SDL_BUTTON_RIGHT, SDL_BUTTON_MIDDLE,
		};
		const std::uint32_t mouse_target = deliver_gameplay
		    ? (mouse_desired_buttons_ & ~mouse_repress_mask_) : 0;
		for (std::size_t index = 0; index < mouse_buttons.size() && budget != 0; ++index) {
			const std::uint32_t bit = 1U << index;
			if ((mouse_delivered_buttons_ & bit) == (mouse_target & bit)) continue;
			SDL_Event event {};
			const bool pressed = (mouse_target & bit) != 0;
			event.type = pressed ? SDL_MOUSEBUTTONDOWN : SDL_MOUSEBUTTONUP;
			event.button.button = mouse_buttons[index];
			event.button.state = pressed ? SDL_PRESSED : SDL_RELEASED;
			event.button.clicks = 1;
			event.button.x = mouse_x_;
			event.button.y = mouse_y_;
			if (PushEvent(event) != EventPushResult::Queued) break;
			if (pressed) mouse_delivered_buttons_ |= bit;
			else mouse_delivered_buttons_ &= ~bit;
			--budget;
		}

		if (overflow_refocus_pending_ && !requested_focus_ && !delivered_focus_ && !AnyDeliveredInput()) {
			overflow_refocus_pending_ = false;
			requested_focus_ = true;
			if (budget != 0) {
				SDL_Event event {};
				event.type = SDL_WINDOWEVENT;
				event.window.event = SDL_WINDOWEVENT_FOCUS_GAINED;
				if (PushEvent(event) == EventPushResult::Queued)
					delivered_focus_ = true;
			}
		}
	}

	void PushKeyboard(const transport::InputEvent &input)
	{
		const SDL_Scancode scancode = Ps2Scancode(input.code);
		const auto index = KeyIndex(scancode);
		if (!index.has_value()) return;
		const bool pressed = input.value0 != 0;
		const bool was_pressed = keyboard_desired_[*index];
		keyboard_desired_[*index] = pressed;
		if (!pressed) {
			keyboard_repress_[*index] = false;
			text_pending_[*index] = false;
		} else if (!was_pressed) {
			// ReconcileInputState decides whether the keydown and its text event
			// actually reached SDL. This remains pending when either is filtered.
			text_pending_[*index] = true;
		}
		if (scancode == SDL_SCANCODE_CAPSLOCK && pressed && !was_pressed) caps_lock_ = !caps_lock_;
		ReconcileInputState();
	}

	void PushMouse(const transport::InputEvent &input)
	{
		const std::uint32_t buttons = (input.code >> 8U) & 0x7U;
		const std::int32_t dx = input.value0;
		const std::int32_t dy = input.value1;
		mouse_desired_buttons_ = buttons;
		mouse_repress_mask_ &= buttons;
		// The PS/2 deltas are untrusted signed 32-bit values. Widen before
		// adding so an extreme packet cannot invoke signed-overflow UB before
		// the cursor is clamped to the framebuffer bounds.
		const auto next_x = static_cast<std::int64_t>(mouse_x_) + static_cast<std::int64_t>(dx);
		const auto next_y = static_cast<std::int64_t>(mouse_y_) + static_cast<std::int64_t>(dy);
		mouse_x_ = static_cast<std::int32_t>(std::clamp<std::int64_t>(
			next_x, 0, static_cast<std::int64_t>(transport::FRAME_WIDTH - 1U)));
		mouse_y_ = static_cast<std::int32_t>(std::clamp<std::int64_t>(
			next_y, 0, static_cast<std::int64_t>(transport::FRAME_HEIGHT - 1U)));
		if (requested_focus_ && delivered_focus_ && (dx != 0 || dy != 0)) {
			SDL_Event motion {};
			motion.type = SDL_MOUSEMOTION;
			motion.motion.which = 0;
			motion.motion.state = MouseButtonMask(mouse_desired_buttons_ & ~mouse_repress_mask_);
			motion.motion.x = mouse_x_;
			motion.motion.y = mouse_y_;
			motion.motion.xrel = dx;
			motion.motion.yrel = dy;
			(void)PushEvent(motion);
		}
		const auto wheel = static_cast<std::int8_t>(input.code & 0xffU);
		if (requested_focus_ && delivered_focus_ && wheel != 0) {
			SDL_Event scroll {};
			scroll.type = SDL_MOUSEWHEEL;
			scroll.wheel.which = 0;
			scroll.wheel.x = 0;
			scroll.wheel.y = wheel;
			scroll.wheel.direction = SDL_MOUSEWHEEL_NORMAL;
			(void)PushEvent(scroll);
		}
		ReconcileInputState();
	}

	void PushJoystick(const transport::InputEvent &input)
	{
		const std::uint32_t buttons = static_cast<std::uint32_t>(input.buttons);
		std::uint32_t desired = buttons & 0xffffU;
		const auto left = static_cast<std::uint16_t>(input.value0);
		const auto right = static_cast<std::uint16_t>(input.value1);
		const auto left_x = static_cast<std::int8_t>(left & 0xffU);
		const auto left_y = static_cast<std::int8_t>((left >> 8U) & 0xffU);
		const auto right_x = static_cast<std::int8_t>(right & 0xffU);
		const auto right_y = static_cast<std::int8_t>((right >> 8U) & 0xffU);
		if (left_x > 32 || right_x > 32) desired |= 1U << 0;
		if (left_x < -32 || right_x < -32) desired |= 1U << 1;
		if (left_y > 32 || right_y > 32) desired |= 1U << 2;
		if (left_y < -32 || right_y < -32) desired |= 1U << 3;
		joystick_desired_mask_ = desired;
		joystick_repress_mask_ &= desired;
		ReconcileInputState();
	}

	void PushFocus(bool focused)
	{
		requested_focus_ = focused;
		if (!focused) {
			for (std::size_t index = 0; index < keyboard_desired_.size(); ++index) {
				keyboard_repress_[index] = keyboard_repress_[index] || keyboard_desired_[index];
				text_pending_[index] = false;
			}
			joystick_repress_mask_ |= joystick_desired_mask_;
			mouse_repress_mask_ |= mouse_desired_buttons_;
		}
		ReconcileInputState();
	}

	void RecoverInputAfterDiscontinuity()
	{
		keyboard_desired_.fill(false);
		keyboard_repress_.fill(false);
		joystick_desired_mask_ = 0;
		joystick_repress_mask_ = 0;
		mouse_desired_buttons_ = 0;
		mouse_repress_mask_ = 0;
		requested_focus_ = false;
		overflow_refocus_pending_ = true;
		ReconcileInputState();
	}

	void ResetInputState()
	{
		keyboard_desired_.fill(false);
		keyboard_repress_.fill(false);
		text_pending_.fill(false);
		keyboard_delivered_.fill(false);
		joystick_desired_mask_ = 0;
		joystick_repress_mask_ = 0;
		mouse_desired_buttons_ = 0;
		mouse_repress_mask_ = 0;
		mouse_delivered_buttons_ = 0;
		requested_focus_ = true;
		delivered_focus_ = true;
		overflow_refocus_pending_ = false;
		caps_lock_ = false;
		input_push_drops_ = 0;
		input_push_filtered_ = 0;
	}

	static bool InputTraceEnabled()
	{
		static const bool enabled = [] {
			const char *value = std::getenv("DIABLO_MISTER_INPUT_TRACE");
			return value != nullptr && (std::strcmp(value, "1") == 0
			                            || std::strcmp(value, "true") == 0);
		}();
		return enabled;
	}

	static void TraceInput(const transport::InputEvent &input)
	{
		if (!InputTraceEnabled()) return;
		std::fprintf(stderr, "Diablo MiSTer input event type=%u code=0x%08x value0=%d value1=%d buttons=0x%016llx\n",
		             input.type, input.code, input.value0, input.value1,
		             static_cast<unsigned long long>(input.buttons));
	}

	void PumpInput()
	{
		auto runtime = Runtime();
		if (!runtime) return;
		std::array<transport::InputEvent, 64> scratch {};
		auto consumed = runtime->session().PollInput(scratch);
		if (!consumed.has_value()) {
			if (consumed.error() == transport::AttachError::InputOverflow) {
				if (InputTraceEnabled())
					std::fputs("Diablo MiSTer input overflow recovered\n", stderr);
				RecoverInputAfterDiscontinuity();
			} else {
				std::fprintf(stderr, "Diablo MiSTer transport input poll failed: error=%u\n",
				             static_cast<unsigned>(consumed.error()));
			}
			ReconcileInputState();
			(void)runtime->Flush();
			return;
		}
		for (const auto &input : std::span<const transport::InputEvent>(scratch.data(), *consumed)) {
			TraceInput(input);
			switch (input.type) {
			case transport::INPUT_EVENT_KEYBOARD: PushKeyboard(input); break;
			case transport::INPUT_EVENT_MOUSE: PushMouse(input); break;
			case transport::INPUT_EVENT_JOYSTICK: PushJoystick(input); break;
			case transport::INPUT_EVENT_FOCUS: PushFocus(input.value0 == 0); break;
			default: break;
			}
		}
		ReconcileInputState();
		(void)runtime->Flush();
	}

	Adapter() = default;
	// Atomic shared ownership lets an in-flight audio callback finish against the
	// old mapping while Shutdown detaches it from all future callbacks.
	std::atomic<std::shared_ptr<transport::TransportRuntime>> runtime_;
	std::atomic<std::uint32_t> audio_reset_generation_ {1};
	std::uint32_t resample_generation_ = 0;
	bool startup_waited_ = false;
	std::uint32_t input_push_drops_ = 0;
	std::uint32_t input_push_filtered_ = 0;
	std::atomic<std::uint32_t> audio_callbacks_inflight_ {0};
	std::atomic<std::uint32_t> runtime_transition_generation_ {0};
	std::atomic<std::uint32_t> pcm_publish_notices_ {0};
	std::atomic<std::uint32_t> pcm_drop_notices_ {0};
	std::atomic<std::uint64_t> pcm_published_frames_ {0};
	std::atomic<std::uint64_t> pcm_dropped_frames_ {0};
	transport::PcmHealth pcm_health_ {};
	bool pcm_health_valid_ = false;
	std::uint32_t pcm_health_poll_count_ = 0;
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
	std::array<PcmFrame, kMaxSourceFrames> resample_input_ {};
	std::array<std::byte, kMaxOutputFrames * 4U> resample_output_ {};
	std::shared_ptr<std::array<std::uint8_t, transport::FRAME_PIXEL_BYTES>[]> command_shadows_ =
	    std::make_shared<std::array<std::uint8_t, transport::FRAME_PIXEL_BYTES>[]>(transport::FRAME_SLOTS);
	std::array<bool, transport::FRAME_SLOTS> command_shadow_valid_ {};
	std::uint32_t command_next_slot_ = 0;
	std::uint64_t command_attempt_fence_ = 1;
	CommandSubmission command_submission_ {};
	bool command_scene_faulted_ = false;
	PcmFrame resample_previous_ {};
	std::uint64_t resample_position_ = 0;
	bool resample_have_previous_ = false;
	std::array<bool, SDL_NUM_SCANCODES> keyboard_desired_ {};
	std::array<bool, SDL_NUM_SCANCODES> keyboard_repress_ {};
	std::array<bool, SDL_NUM_SCANCODES> text_pending_ {};
	std::array<bool, SDL_NUM_SCANCODES> keyboard_delivered_ {};
	std::uint32_t joystick_desired_mask_ = 0;
	std::uint32_t joystick_repress_mask_ = 0;
	std::uint32_t mouse_desired_buttons_ = 0;
	std::uint32_t mouse_repress_mask_ = 0;
	std::uint32_t mouse_delivered_buttons_ = 0;
	bool requested_focus_ = true;
	bool delivered_focus_ = true;
	bool overflow_refocus_pending_ = false;
	bool caps_lock_ = false;
	std::int32_t mouse_x_ = transport::FRAME_WIDTH / 2;
	std::int32_t mouse_y_ = transport::FRAME_HEIGHT / 2;
};

inline bool Initialize() { return Adapter::Instance().Initialize(); }
inline void Shutdown() { Adapter::Instance().Shutdown(); }
inline bool Active() { return Adapter::Instance().Active(); }
inline bool Requested() { return Adapter::Instance().Requested(); }
inline bool CpuPacingEnabled() { return Adapter::Instance().CpuPacingEnabled(); }
inline bool Present(SDL_Surface *surface, std::uint64_t logic_tick)
{
	return Adapter::Instance().Present(surface, logic_tick);
}

} // namespace diablo::mister::sdl
