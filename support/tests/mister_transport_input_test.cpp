// SPDX-License-Identifier: GPL-2.0-or-later
#define SDL_MAIN_HANDLED
#include <SDL.h>

#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <vector>

#include "mister_transport_sdl.hpp"

namespace {

using diablo::mister::sdl::Adapter;
using diablo::mister::transport::InputEvent;

[[noreturn]] void Fail(const char *message)
{
	std::fprintf(stderr, "%s\n", message);
	std::exit(EXIT_FAILURE);
}

void Check(bool value, const char *message)
{
	if (!value) Fail(message);
}

void ClearEvents()
{
	SDL_FlushEvents(SDL_FIRSTEVENT, SDL_LASTEVENT);
}

std::vector<SDL_Event> Events()
{
	std::vector<SDL_Event> events;
	SDL_Event event {};
	while (SDL_PollEvent(&event) == 1) events.push_back(event);
	return events;
}

InputEvent Keyboard(std::uint32_t scan, bool pressed)
{
	InputEvent event {};
	event.type = diablo::mister::transport::INPUT_EVENT_KEYBOARD;
	event.code = scan;
	event.value0 = pressed ? 1 : 0;
	return event;
}

InputEvent Mouse(std::uint32_t buttons, std::int32_t dx, std::int32_t dy)
{
	InputEvent event {};
	event.type = diablo::mister::transport::INPUT_EVENT_MOUSE;
	event.code = buttons << 8U;
	event.value0 = dx;
	event.value1 = dy;
	return event;
}

InputEvent Joystick(std::uint32_t buttons)
{
	InputEvent event {};
	event.type = diablo::mister::transport::INPUT_EVENT_JOYSTICK;
	event.buttons = buttons;
	return event;
}


int FilterKeyboardDown(void *, SDL_Event *event)
{
	return event->type != SDL_KEYDOWN;
}

int FilterTextInput(void *, SDL_Event *event)
{
	return event->type != SDL_TEXTINPUT;
}

} // namespace

namespace diablo::mister::sdl {

class InputAdapterTest {
public:
	static int Run()
	{
	#ifdef _WIN32
		_putenv_s("DIABLO_MISTER_PROFILE", "1");
	#else
		setenv("DIABLO_MISTER_PROFILE", "1", 1);
	#endif
	SDL_SetMainReady();
	if (SDL_Init(SDL_INIT_EVENTS) != 0) Fail(SDL_GetError());
	auto &adapter = Adapter::Instance();
	adapter.lifecycle_.runtime_transition_generation_.store(0, std::memory_order_release);
	adapter.lifecycle_.audio_callbacks_inflight_.store(0, std::memory_order_release);
	Check(adapter.BeginAudioCallback(), "audio callback did not acquire a stable runtime generation");
	Check(!adapter.BeginRuntimeTransition(), "recovery entered while an audio callback held the runtime");
	adapter.lifecycle_.audio_callbacks_inflight_.fetch_sub(1, std::memory_order_release);
	Check(adapter.BeginRuntimeTransition(), "recovery did not acquire the transition gate");
	Check(!adapter.BeginAudioCallback(), "audio callback entered during a runtime transition");
	adapter.EndRuntimeTransition();
	Check(adapter.BeginAudioCallback(), "audio callback did not resume after a runtime transition");
	adapter.lifecycle_.audio_callbacks_inflight_.fetch_sub(1, std::memory_order_release);

	// ResetProfile owns every profiler counter, including command metrics. The
	// command-build helper must reject unavailable/backward timestamps without
	// creating a wrapped duration sample.
	adapter.profile_.command_scene_attempts_ = 3;
	adapter.profile_.command_scene_no_slot_ = 4;
	adapter.profile_.command_scene_overflow_ = 5;
	adapter.profile_.command_scene_publish_failures_ = 6;
	adapter.profile_.command_scene_fence_failures_ = 7;
	adapter.profile_.command_scene_frame_failures_ = 8;
	adapter.profile_.command_scene_batches_ = 9;
	adapter.profile_.command_build_count_ = 4;
	adapter.profile_.command_build_total_ns_ = 5;
	adapter.profile_.command_build_max_ns_ = 6;
	adapter.profile_.command_wait_count_ = 5;
	adapter.profile_.command_wait_total_ns_ = 6;
	adapter.profile_.command_wait_max_ns_ = 7;
	adapter.profile_.ResetProfile();
	Check(adapter.profile_.command_scene_attempts_ == 0
	          && adapter.profile_.command_scene_no_slot_ == 0
	          && adapter.profile_.command_scene_overflow_ == 0
	          && adapter.profile_.command_scene_publish_failures_ == 0
	          && adapter.profile_.command_scene_fence_failures_ == 0
	          && adapter.profile_.command_scene_frame_failures_ == 0
	          && adapter.profile_.command_scene_batches_ == 0
	          && adapter.profile_.command_build_count_ == 0
	          && adapter.profile_.command_build_total_ns_ == 0
	          && adapter.profile_.command_build_max_ns_ == 0
	          && adapter.profile_.command_wait_count_ == 0
	          && adapter.profile_.command_wait_total_ns_ == 0
	          && adapter.profile_.command_wait_max_ns_ == 0,
	      "profile reset retained command metrics");
	adapter.profile_.RecordCommandBuild(100, 0);
	adapter.profile_.RecordCommandBuild(100, 99);
	Check(adapter.profile_.command_build_count_ == 0
	          && adapter.profile_.command_build_total_ns_ == 0,
	      "invalid command-build timestamps created a sample");
	adapter.profile_.RecordCommandBuild(100, 125);
	Check(adapter.profile_.command_build_count_ == 1
	          && adapter.profile_.command_build_total_ns_ == 25
	          && adapter.profile_.command_build_max_ns_ == 25,
	      "valid command-build timestamp was not recorded");

	// Fixed deadlines absorb oversleep; whole-frame hitches discard backlog.
	adapter.ResetFramePacing();
	Check(!adapter.frame_pacing_.Initialized() && adapter.frame_pacing_.Last() == 0,
	      "frame pacing reset retained state");
	std::uint64_t clock = 0;
	auto now = [&] { return clock; };
	auto sleep = [&](std::uint64_t ticks) { clock += ticks; };
	auto &pacer = adapter.frame_pacing_;
	pacer.PaceWithClock(1000000000ULL, now, sleep);
	Check(clock == 0, "first frame added unnecessary latency");
	for (unsigned frame = 0; frame < 60; ++frame) {
		const auto previous = clock;
		clock += 4000000; // Work counts towards the period, not an extra delay.
		pacer.PaceWithClock(1000000000ULL, now, sleep);
		Check(clock - previous == 16666667, "frame did not respect 60 Hz cap");
	}
	clock += 100000000;
	const auto hitch = clock;
	pacer.PaceWithClock(1000000000ULL, now, sleep);
	Check(clock == hitch, "slow frame added another sleep");
	pacer.PaceWithClock(1000000000ULL, now, sleep);
	Check(clock == hitch + 16666667, "hitch caused a catch-up burst");
	pacer.PaceWithClock(1000000000ULL, now,
	    [&](std::uint64_t ticks) { clock += ticks + 2000000; });
	const auto overslept = clock;
	pacer.PaceWithClock(1000000000ULL, now, sleep);
	Check(clock - overslept == 14666667, "oversleep drifted the next deadline");
	unsigned early_wakes = 0;
	const auto before_early = clock;
	pacer.PaceWithClock(1000000000ULL, now, [&](std::uint64_t ticks) {
		clock += early_wakes++ == 0 ? ticks / 2 : ticks;
	});
	Check(early_wakes == 2 && clock - before_early == 16666667,
	      "early wake bypassed the frame cap");

	// Follow a scanout cadence that differs from 60 Hz, including counter wrap.
	pacer.Reset();
	clock = 0;
	std::uint32_t scanout = 0xFFFFFFFFU;
	auto feedback = [&] { return scanout; };
	pacer.PaceWithFeedbackClock(1000000000ULL, now, sleep, feedback);
	clock = 5000000;
	pacer.PaceWithFeedbackClock(1000000000ULL, now, [&](std::uint64_t ticks) {
		clock += ticks;
		if (clock >= 17000000) scanout = 0;
	}, feedback);
	Check(clock == 17000000, "presentation feedback did not track scanout/wrap");
	clock = 22000000;
	pacer.PaceWithFeedbackClock(1000000000ULL, now, [&](std::uint64_t ticks) {
		clock += ticks;
		if (clock >= 34000000) scanout = 1;
	}, feedback);
	Check(clock == 34000000, "software clock competed with scanout feedback");
	const auto stalled = clock;
	pacer.PaceWithFeedbackClock(1000000000ULL, now, sleep, feedback);
	Check(clock - stalled == 25000000, "stalled FPGA blocked recovery beyond timeout");
	pacer.Reset();
	const auto reset_time = clock;
	pacer.PaceWithFeedbackClock(1000000000ULL, now, sleep, feedback);
	Check(clock == reset_time, "reset retained an old presentation sequence");

	// A core reload resets every ABI frame slot. Adapter-side command shadows
	// Timeout and late completion belong to one wait sample. Invalid clock
	// readings must not underflow the distribution or consume that sample.
	adapter.profile_.command_wait_count_ = 0;
	adapter.profile_.command_wait_total_ns_ = 0;
	adapter.profile_.command_wait_max_ns_ = 0;
	adapter.command_frames_.command_submission_ = {};
	adapter.command_frames_.command_submission_.submitted_ns = 100;
	adapter.command_frames_.RecordCommandWait(0, adapter.profile_);
	adapter.command_frames_.RecordCommandWait(99, adapter.profile_);
	Check(adapter.profile_.command_wait_count_ == 0, "invalid clock created command wait sample");
	adapter.command_frames_.command_submission_.timed_out = true;
	adapter.command_frames_.RecordCommandWait(125, adapter.profile_); // timeout observation
	adapter.command_frames_.RecordCommandWait(175, adapter.profile_); // late fence observation
	Check(adapter.profile_.command_wait_count_ == 1 && adapter.profile_.command_wait_total_ns_ == 25
	          && adapter.profile_.command_wait_max_ns_ == 25,
	      "late fence counted a timed-out command wait twice");
	adapter.ResetCommandSceneState();
	adapter.command_frames_.command_submission_.submitted_ns = 200;
	adapter.command_frames_.RecordCommandWait(240, adapter.profile_);
	Check(adapter.profile_.command_wait_count_ == 2 && adapter.profile_.command_wait_total_ns_ == 65
	          && adapter.profile_.command_wait_max_ns_ == 40,
	      "new command submission failed to record a new wait");

	// A core reload resets every ABI frame slot. Adapter-side command shadows
	// must be discarded with that epoch or the next changed-run submission could
	// omit pixels that no longer exist in the freshly cleared slot.
	adapter.command_frames_.command_shadow_valid_.fill(true);
	CommandFrameState independent_commands;
	independent_commands.command_shadow_valid_.fill(true);
	independent_commands.command_submission_.active = true;
	independent_commands.command_submission_.timed_out = true;
	adapter.command_frames_.command_next_slot_ = 2;
	adapter.command_frames_.command_attempt_fence_ = 99;
	adapter.command_frames_.command_submission_.active = true;
	adapter.command_frames_.command_scene_faulted_ = true;
	adapter.ResetCommandSceneState();
	Check(independent_commands.command_submission_.active
	          && independent_commands.command_submission_.timed_out
	          && independent_commands.command_shadow_valid_[0],
	      "reset mutated a different command owner's pending submission");
	for (unsigned cycle = 0; cycle < 64; ++cycle) {
		independent_commands.command_submission_.active = true;
		independent_commands.command_submission_.timed_out = true;
		independent_commands.command_shadow_valid_.fill(true);
		independent_commands.Reset();
		Check(!independent_commands.command_submission_.active
		          && !independent_commands.command_submission_.timed_out
		          && !independent_commands.command_shadow_valid_[0]
		          && independent_commands.command_attempt_fence_ == 1,
		      "command epoch reset retained pending ownership or cached content");
	}
	Check(!adapter.command_frames_.command_shadow_valid_[0] && !adapter.command_frames_.command_shadow_valid_[1]
	          && !adapter.command_frames_.command_shadow_valid_[2]
	          && adapter.command_frames_.command_next_slot_ == 0 && adapter.command_frames_.command_attempt_fence_ == 1
	          && !adapter.command_frames_.command_submission_.active && !adapter.command_frames_.command_scene_faulted_,
	      "command scene state was not reset with the transport epoch");

	// PS/2 bit 1 means right mouse, but SDL motion uses SDL_BUTTON_RMASK (4),
	// not the raw PS/2 mask (2).
	adapter.input_.ResetInputState();
	ClearEvents();
	adapter.input_.PushMouse(Mouse(0x2, 3, -2));
	auto events = Events();
	Check(events.size() == 2, "right-mouse packet did not publish motion and edge");
	Check(events[0].type == SDL_MOUSEMOTION && events[0].motion.state == SDL_BUTTON_RMASK,
	      "motion did not translate the PS/2 right-button mask");
	Check(events[1].type == SDL_MOUSEBUTTONDOWN && events[1].button.button == SDL_BUTTON_RIGHT,
	      "right-button edge was not translated");

	// Extreme signed deltas must clamp without overflowing the cursor addition.
	adapter.input_.ResetInputState();
	adapter.input_.mouse_x_ = 0;
	adapter.input_.mouse_y_ = 0;
	ClearEvents();
	adapter.input_.PushMouse(Mouse(0, std::numeric_limits<std::int32_t>::max(),
	                        std::numeric_limits<std::int32_t>::min()));
	Check(adapter.input_.mouse_x_ == static_cast<std::int32_t>(diablo::mister::transport::FRAME_WIDTH - 1U)
	          && adapter.input_.mouse_y_ == 0,
	      "extreme mouse deltas did not clamp safely");
	ClearEvents();

	// OSD focus loss releases delivered state and forces a neutral/repress cycle.
	adapter.input_.ResetInputState();
	ClearEvents();
	adapter.input_.PushKeyboard(Keyboard(0x1d, true)); // W
	Check(Events().size() == 1, "initial keyboard press was not delivered");
	adapter.input_.PushFocus(false);
	events = Events();
	Check(events.size() == 2 && events[0].type == SDL_WINDOWEVENT
	          && events[0].window.event == SDL_WINDOWEVENT_FOCUS_LOST
	          && events[1].type == SDL_KEYUP,
	      "focus loss did not publish an ordered release");
	adapter.input_.PushFocus(true);
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_WINDOWEVENT
	          && events[0].window.event == SDL_WINDOWEVENT_FOCUS_GAINED,
	      "focus gain did not publish focus only");
	adapter.input_.PushKeyboard(Keyboard(0x1d, false));
	Check(Events().empty(), "release after focus gain should only arm a future repress");
	adapter.input_.PushKeyboard(Keyboard(0x1d, true));
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_KEYDOWN,
	      "key did not require neutral then re-press after focus gain");

	// SDL filtering must leave the desired state pending until a later reconcile
	// can queue the actual engine event.
	adapter.input_.ResetInputState();
	ClearEvents();
	SDL_SetEventFilter(FilterKeyboardDown, nullptr);
	adapter.input_.PushKeyboard(Keyboard(0x1d, true));
	Check(!adapter.input_.keyboard_delivered_[SDL_SCANCODE_W], "filtered key was marked delivered");
	SDL_SetEventFilter(nullptr, nullptr);
	adapter.input_.ReconcileInputState();
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_KEYDOWN
	          && adapter.input_.keyboard_delivered_[SDL_SCANCODE_W],
	      "filtered key was not recovered by bounded reconciliation");

	// Controller buttons must not impersonate or retain physical keyboard keys.
	adapter.input_.ResetInputState();
	ClearEvents();
	adapter.input_.PushKeyboard(Keyboard(0x11, true)); // left Alt
	adapter.input_.PushJoystick(Joystick(1U << 4));    // controller A, not left Alt
	ClearEvents();
	adapter.input_.PushKeyboard(Keyboard(0x11, false));
	Check(!adapter.input_.KeyWanted(SDL_SCANCODE_LALT), "controller retained physical left Alt");
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_KEYUP,
	      "physical Alt release was masked by controller A");
	adapter.input_.PushJoystick(Joystick(0));
	events = Events();
	Check(events.empty(), "controller release emitted a keyboard event");

	// Text is emitted only while SDL has text input active, using the aggregate
	// physical modifier state. Controller modifiers do not affect typed text.
	adapter.input_.ResetInputState();
	ClearEvents();
	SDL_StartTextInput();
	adapter.input_.PushKeyboard(Keyboard(0x12, true)); // left Shift
	Check((SDL_GetModState() & KMOD_LSHIFT) != 0, "physical Shift missing from polled SDL modifiers");
	adapter.input_.PushKeyboard(Keyboard(0x1c, true)); // A
	events = Events();
	Check(events.size() == 3 && events[0].type == SDL_KEYDOWN && events[1].type == SDL_KEYDOWN
	          && (events[1].key.keysym.mod & KMOD_SHIFT) != 0 && events[2].type == SDL_TEXTINPUT
	          && std::strcmp(events[2].text.text, "A") == 0,
	      "shifted text input did not follow physical modifier state");
	SDL_StopTextInput();

	// A queued keydown does not prove that the paired text event reached the
	// engine. Keep the character pending when SDL filters it, then deliver it
	// exactly once after the filter is removed.
	adapter.input_.ResetInputState();
	ClearEvents();
	SDL_StartTextInput();
	SDL_SetEventFilter(FilterTextInput, nullptr);
	adapter.input_.PushKeyboard(Keyboard(0x1c, true)); // A
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_KEYDOWN
	          && adapter.input_.text_pending_[SDL_SCANCODE_A],
	      "filtered text input was not retained after its keydown");
	SDL_SetEventFilter(nullptr, nullptr);
	adapter.input_.ReconcileInputState();
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_TEXTINPUT
	          && std::strcmp(events[0].text.text, "a") == 0
	          && !adapter.input_.text_pending_[SDL_SCANCODE_A],
	      "pending text input was not recovered exactly once");
	adapter.input_.PushKeyboard(Keyboard(0x1c, false));
	Check(Events().size() == 1, "key release after recovered text was not delivered");
	SDL_StopTextInput();

	// Independent owners must not share desired/delivered state. Repeated
	// reset cycles must still deliver exactly one press and release each.
	InputReconciler first;
	InputReconciler second;
	for (unsigned cycle = 0; cycle < 64; ++cycle) {
		first.ResetInputState();
		second.ResetInputState();
		ClearEvents();
		first.PushKeyboard(Keyboard(0x1d, true));
		Check(Events().size() == 1, "reset cycle lost or duplicated key press");
		second.ResetInputState();
		Check(first.keyboard_delivered_[SDL_SCANCODE_W]
		          && !second.keyboard_delivered_[SDL_SCANCODE_W],
		      "input owners share delivered state");
		first.PushKeyboard(Keyboard(0x1d, false));
		auto released = Events();
		Check(released.size() == 1 && released[0].type == SDL_KEYUP,
		      "reset cycle lost or duplicated key release");
		second.ReconcileInputState();
		Check(Events().empty(), "idle input owner emitted another owner's events");
	}

	SDL_Quit();
	// Audio chunk boundaries must not change the resampled stream. Resetting
	// the generation must produce exactly the same output as a fresh owner.
	std::vector<std::uint8_t> pcm(1024 * 4);
	for (std::size_t i = 0; i < pcm.size(); ++i)
		pcm[i] = static_cast<std::uint8_t>((i * 37U + i / 7U) & 255U);
	auto whole = std::make_unique<PcmResampler>();
	auto split = std::make_unique<PcmResampler>();
	const auto converted = whole->Convert(pcm.data(), pcm.size(), 1);
	Check(converted.has_value(), "whole PCM conversion failed");
	std::vector<std::byte> expected(converted->begin(), converted->end());
	std::vector<std::byte> actual;
	for (std::size_t offset = 0; offset < pcm.size();) {
		const auto bytes = std::min<std::size_t>(pcm.size() - offset, 4U * (1U + offset % 53U));
		const auto chunk = split->Convert(pcm.data() + offset, bytes, 1);
		Check(chunk.has_value(), "split PCM conversion failed");
		actual.insert(actual.end(), chunk->begin(), chunk->end());
		offset += bytes;
	}
	Check(actual == expected, "PCM callback boundaries changed sample bytes");
	for (std::uint32_t generation = 2; generation < 66; ++generation) {
		const auto reset = split->Convert(pcm.data(), pcm.size(), generation);
		Check(reset && std::vector<std::byte>(reset->begin(), reset->end()) == expected,
		      "PCM reset retained previous-stream interpolation history");
	}
	Check(!split->Convert(nullptr, 4, 66), "PCM null input accepted");
	Check(!split->Convert(pcm.data(), 3, 66), "PCM partial frame accepted");
	Check(!split->Convert(pcm.data(), 8193U * 4U, 66), "PCM oversized callback accepted");
	std::puts("transport input reconciliation checks passed");
	return EXIT_SUCCESS;
}

};

class TransportProfileTest {
public:
	static void Run(Adapter &adapter)
	{
		std::remove("transport-profile-trace-test.jsonl");
	#ifdef _WIN32
		_putenv_s("DIABLO_MISTER_PROFILE_TRACE", "transport-profile-trace-test.jsonl");
	#else
		setenv("DIABLO_MISTER_PROFILE_TRACE", "transport-profile-trace-test.jsonl", 1);
	#endif
		adapter.profile_.ResetProfile();
		const auto start = adapter.profile_.NowNs();
		Check(start != 0, "monotonic clock was unavailable for profile accounting");
		adapter.profile_.RecordProfile(start, false, true, Adapter::ProfileOutcome::PublishFailed);
		Check(adapter.profile_.profile_present_count_ == 1, "failed presentation was not counted");
		Check(adapter.profile_.profile_published_count_ == 0, "failed presentation was counted as published");
		Check(adapter.profile_.profile_backpressure_count_ == 1, "backpressure was not retained on publish failure");
		Check(adapter.profile_.profile_outcome_counts_[static_cast<std::size_t>(Adapter::ProfileOutcome::PublishFailed)] == 1,
		      "publish-failure outcome was not counted");
		adapter.profile_.RecordProfile(0, false, false, Adapter::ProfileOutcome::RuntimeUnavailable);
		Check(adapter.profile_.profile_present_count_ == 2 && adapter.profile_.profile_timing_invalid_count_ == 1,
		      "invalid monotonic sample was not retained as an outcome");
		Check(adapter.profile_.EmitProfileTrace(), "profile trace write unexpectedly failed");
		Check(!adapter.profile_.profile_trace_write_failed_, "successful profile trace was marked failed");
		std::FILE *trace = std::fopen("transport-profile-trace-test.jsonl", "rb");
		Check(trace != nullptr, "profile trace was not written");
		char contents[2048] {};
		const auto bytes = std::fread(contents, 1, sizeof(contents) - 1, trace);
		std::fclose(trace);
		Check(bytes > 0 && std::strstr(contents, "diablo-presentation-trace-v1") != nullptr
		          && std::strstr(contents, "publish_failed") != nullptr
		          && std::strstr(contents, "runtime_unavailable") != nullptr
		          && std::strstr(contents, "timing_invalid_records\":1") != nullptr,
		      "profile trace did not preserve mixed outcomes and invalid timing");
		Check(!adapter.profile_.EmitProfileTrace() && adapter.profile_.profile_trace_write_failed_,
		      "profile trace silently replaced an existing evidence path");
		std::remove("transport-profile-trace-test.jsonl");
		adapter.profile_.ResetProfile();
		for (std::size_t index = 0; index < TransportProfiler::kProfileTraceCapacity + 2; ++index)
			adapter.profile_.RecordProfile(start, false, false, Adapter::ProfileOutcome::BackpressureDropped);
		Check(adapter.profile_.profile_trace_count_ == TransportProfiler::kProfileTraceCapacity
		          && adapter.profile_.profile_trace_dropped_ == 2,
		      "bounded trace did not count overwritten telemetry records");
		Check(adapter.profile_.EmitProfileTrace(), "overflow profile trace write unexpectedly failed");
		trace = std::fopen("transport-profile-trace-test.jsonl", "rb");
		Check(trace != nullptr, "overflow profile trace was not written");
		std::memset(contents, 0, sizeof(contents));
		const auto overflow_bytes = std::fread(contents, 1, sizeof(contents) - 1, trace);
		std::fclose(trace);
		Check(overflow_bytes > 0 && std::strstr(contents, "\"records\":4096") != nullptr
		          && std::strstr(contents, "\"dropped_records\":2") != nullptr
		          && std::strstr(contents, "\"sequence\":2") != nullptr,
		      "overflow trace did not retain the newest bounded window");
		std::remove("transport-profile-trace-test.jsonl");
	}
};

} // namespace diablo::mister::sdl

int main()
{
	const int status = diablo::mister::sdl::InputAdapterTest::Run();
	if (status == EXIT_SUCCESS)
		diablo::mister::sdl::TransportProfileTest::Run(diablo::mister::sdl::Adapter::Instance());
	return status;
}
