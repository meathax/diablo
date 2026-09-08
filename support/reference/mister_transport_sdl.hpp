#pragma once

#include "mister_command_scene.hpp"
#include "mister_command_transport.hpp"
#include "mister_transport_config.hpp"
#include "mister_transport_input.hpp"
#include "mister_pcm_resampler.hpp"
#include "mister_command_frame_state.hpp"
#include "mister_transport_profiler.hpp"
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
	using ProfileOutcome = TransportProfiler::ProfileOutcome;

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
		profile_.ResetProfile();
		ResetCommandSceneState();
		input_.ResetInputState();
		ResetFramePacing();
		return true;
	}

	void Shutdown()
	{
		profile_.EmitProfile();
		(void)profile_.EmitProfileTrace();
		// Audio callbacks take their own shared runtime reference. Releasing the
		// adapter's reference first prevents any new callback from mapping/writing
		// the old epoch while an in-flight callback keeps its mapping alive.
		(void)runtime_.exchange(std::shared_ptr<transport::TransportRuntime> {},
		                        std::memory_order_acq_rel);
		startup_waited_ = false;
		RequestAudioReset();
		ResetCommandSceneState();
		input_.ResetInputState();
		ResetFramePacing();
	}

	[[nodiscard]] bool Active() const { return static_cast<bool>(Runtime()); }

	[[nodiscard]] bool CpuPacingEnabled() const
	{
		const char *value = std::getenv("DIABLO_MISTER_NO_CPU_PACING");
		return value == nullptr || (std::strcmp(value, "0") == 0
		                            || std::strcmp(value, "false") == 0);
	}

	[[nodiscard]] bool ForceFramePacing() const
	{
		const char *value = std::getenv("DIABLO_MISTER_FORCE_FRAME_PACING");
		return value != nullptr && (std::strcmp(value, "1") == 0
		                            || std::strcmp(value, "true") == 0);
	}

	// Timedemo mode intentionally disables DevilutionX's normal frame limiter.
	// That is useful on a desktop, but it can flood the finite MiSTer frame ring
	// and starve the target service path. The target launcher opts into this
	// bounded 60 Hz deadline whenever --timedemo is requested.
	void PaceFrame()
	{
		const std::uint32_t now = SDL_GetTicks();
		if (!frame_pacing_initialized_ || FramePacingIsLate(now, frame_pacing_deadline_, 1000U)) {
			frame_pacing_initialized_ = true;
			frame_pacing_deadline_ = now;
			frame_pacing_fraction_ = 0;
		}
		const std::uint32_t target = AdvanceFramePacingDeadline(
			frame_pacing_deadline_, frame_pacing_fraction_);
		if (static_cast<std::int32_t>(target - now) > 0)
			SDL_Delay(target - now);
		const std::uint32_t after = SDL_GetTicks();
		if (FramePacingIsLate(after, target, 1000U)) {
			frame_pacing_deadline_ = after;
			frame_pacing_fraction_ = 0;
		} else {
			frame_pacing_deadline_ = target;
		}
	}

	// Copies the engine's native indexed surface into one ABI frame slot. The
	// caller remains the pacing authority; a short bounded wait handles an FPGA
	// consumer that is still retiring the previous three slots.
	[[nodiscard]] bool Present(SDL_Surface *surface, std::uint64_t logic_tick)
	{
		const std::uint64_t profile_start = profile_.ProfileEnabled() ? profile_.NowNs() : 0;
		auto runtime = Runtime();
		if (!runtime) {
			profile_.RecordProfile(profile_start, false, false, ProfileOutcome::RuntimeUnavailable);
			return false;
		}
		const auto fpga_state = std::atomic_ref<std::uint32_t>(
			runtime->session().view().header().fpga_state).load(std::memory_order_acquire);
		if (fpga_state == static_cast<std::uint32_t>(transport::ComponentState::Fault)) {
			if (!BeginRuntimeTransition()) {
				// Gate recovery until every callback that entered its read-side
				// critical section has exited. This is non-blocking on Present.
				profile_.RecordProfile(profile_start, false, false, ProfileOutcome::RecoveryDeferred);
				return false;
			}
			const bool recovered = runtime->RecoverAfterFpgaFault();
			EndRuntimeTransition();
			if (!recovered) {
				profile_.RecordProfile(profile_start, false, false, ProfileOutcome::RecoveryFailed);
				return false;
			}
			std::fputs("Diablo MiSTer transport recovered after FPGA reset\n", stderr);
			startup_waited_ = false;
			RequestAudioReset();
			input_.RecoverInputAfterDiscontinuity();
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
			profile_.RecordProfile(profile_start, false, false, ProfileOutcome::InvalidSurface);
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
			auto command_result = command_frames_.TryPresentCommand(source, static_cast<std::size_t>(surface->pitch), palette, logic_tick, Runtime(), profile_, CommandWaitMs());
			if (command_result.has_value()) {
				FlushProfiled();
				profile_.RecordProfile(profile_start, *command_result, false,
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
			const std::uint64_t publish_start = profile_.ProfileEnabled() ? profile_.NowNs() : 0;
			auto published = runtime->session().PublishIndexedFrame(
				source, static_cast<std::size_t>(surface->pitch), palette, logic_tick);
			profile_.RecordPublish(publish_start);
			if (published.has_value()) {
				if (CommandSceneEnabled())
					command_frames_.RememberFullFrame(*published, source, static_cast<std::size_t>(surface->pitch), Runtime());
				FlushProfiled();
				profile_.RecordProfile(profile_start, true, saw_backpressure, ProfileOutcome::FramePublished);
				return true;
			}
			if (published.error() != transport::PublishError::Backpressure) {
				std::fprintf(stderr, "Diablo MiSTer transport frame publish failed: error=%u\n",
				             static_cast<unsigned>(published.error()));
				FlushProfiled();
				profile_.RecordProfile(profile_start, false, saw_backpressure, ProfileOutcome::PublishFailed);
				return false;
			}
			saw_backpressure = true;
			SDL_Delay(1);
		}
		static std::uint32_t backpressure_drops = 0;
		if ((++backpressure_drops & 63U) == 1U)
			std::fputs("Diablo MiSTer transport frame backpressure; using SDL pacing\n", stderr);
		FlushProfiled();
		profile_.RecordProfile(profile_start, false, saw_backpressure, ProfileOutcome::BackpressureDropped);
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
		const auto converted = resampler_.Convert(bytes, byte_count, audio_generation);
		if (!converted) return false;
		const auto pcm_bytes = *converted;
		const std::size_t output_frames = pcm_bytes.size() / 4U;
		if (output_frames == 0) return true;
		const std::uint32_t epoch = runtime->session().epoch();
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

	void ResetCommandSceneState() { command_frames_.Reset(); }

	static bool FramePacingIsLate(std::uint32_t now, std::uint32_t deadline,
	                             std::uint32_t threshold_ms)
	{
		return static_cast<std::int32_t>(now - deadline)
		       > static_cast<std::int32_t>(threshold_ms);
	}

	static std::uint32_t AdvanceFramePacingDeadline(std::uint32_t deadline,
	                                                std::uint32_t &fraction)
	{
		// 60 Hz is 1000/60 ms. Carry the 40 ms remainder so the integer tick
		// schedule averages exactly 16 2/3 ms rather than truncating to 16 ms.
		fraction += 40U;
		std::uint32_t step = 16U;
		if (fraction >= 60U) {
			fraction -= 60U;
			++step;
		}
		return deadline + step;
	}

	void ResetFramePacing()
	{
		frame_pacing_initialized_ = false;
		frame_pacing_deadline_ = 0;
		frame_pacing_fraction_ = 0;
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
			             "Diablo MiSTer PCM health changed: queued=%u local_queue=%u producer=%u consumer=%u "
			             "underrun=%u resync=%u callbacks=%u drops=%u frames=%llu dropped_frames=%llu\n",
			             health->queued_frames, health->local_queue_frames,
			             health->producer_sequence, health->consumer_sequence,
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


	static bool AudioTraceEnabled()
	{
		static const bool enabled = [] {
			const char *value = std::getenv("DIABLO_MISTER_AUDIO_TRACE");
			return value != nullptr && (std::strcmp(value, "1") == 0
			                            || std::strcmp(value, "true") == 0);
		}();
		return enabled;
	}

	void FlushProfiled()
	{
		auto runtime = Runtime();
		if (!runtime) return;
		const auto start = profile_.ProfileEnabled() ? profile_.NowNs() : 0;
		(void)runtime->Flush();
		profile_.RecordFlush(start);
	}

	void PumpInput()
	{
		auto runtime = Runtime();
		if (!runtime) return;
		std::array<transport::InputEvent, 64> scratch {};
		auto consumed = runtime->session().PollInput(scratch);
		if (!consumed.has_value()) {
			if (consumed.error() == transport::AttachError::InputOverflow) {
				if (input_.InputTraceEnabled())
					std::fputs("Diablo MiSTer input overflow recovered\n", stderr);
				input_.RecoverInputAfterDiscontinuity();
			} else {
				std::fprintf(stderr, "Diablo MiSTer transport input poll failed: error=%u\n",
				             static_cast<unsigned>(consumed.error()));
			}
			input_.ReconcileInputState();
			(void)runtime->Flush();
			return;
		}
		for (const auto &input : std::span<const transport::InputEvent>(scratch.data(), *consumed)) {
			input_.TraceInput(input);
			switch (input.type) {
			case transport::INPUT_EVENT_KEYBOARD: input_.PushKeyboard(input); break;
			case transport::INPUT_EVENT_MOUSE: input_.PushMouse(input); break;
			case transport::INPUT_EVENT_JOYSTICK: input_.PushJoystick(input); break;
			case transport::INPUT_EVENT_FOCUS: input_.PushFocus(input.value0 == 0); break;
			default: break;
			}
		}
		input_.ReconcileInputState();
		(void)runtime->Flush();
	}

	TransportProfiler profile_;
	CommandFrameState command_frames_;
	PcmResampler resampler_;
	InputReconciler input_;
	Adapter() = default;
	// Atomic shared ownership lets an in-flight audio callback finish against the
	// old mapping while Shutdown detaches it from all future callbacks.
	std::atomic<std::shared_ptr<transport::TransportRuntime>> runtime_;
	std::atomic<std::uint32_t> audio_reset_generation_ {1};
	bool startup_waited_ = false;
	std::atomic<std::uint32_t> audio_callbacks_inflight_ {0};
	std::atomic<std::uint32_t> runtime_transition_generation_ {0};
	std::atomic<std::uint32_t> pcm_publish_notices_ {0};
	std::atomic<std::uint32_t> pcm_drop_notices_ {0};
	std::atomic<std::uint64_t> pcm_published_frames_ {0};
	std::atomic<std::uint64_t> pcm_dropped_frames_ {0};
	transport::PcmHealth pcm_health_ {};
	bool pcm_health_valid_ = false;
	std::uint32_t pcm_health_poll_count_ = 0;
	bool frame_pacing_initialized_ = false;
	std::uint32_t frame_pacing_deadline_ = 0;
	std::uint32_t frame_pacing_fraction_ = 0;



};

inline bool Initialize() { return Adapter::Instance().Initialize(); }
inline void Shutdown() { Adapter::Instance().Shutdown(); }
inline bool Active() { return Adapter::Instance().Active(); }
inline bool Requested() { return Adapter::Instance().Requested(); }
inline bool CpuPacingEnabled() { return Adapter::Instance().CpuPacingEnabled(); }
inline bool ForceFramePacing() { return Adapter::Instance().ForceFramePacing(); }
inline void PaceFrame() { Adapter::Instance().PaceFrame(); }
inline bool Present(SDL_Surface *surface, std::uint64_t logic_tick)
{
	return Adapter::Instance().Present(surface, logic_tick);
}

} // namespace diablo::mister::sdl
