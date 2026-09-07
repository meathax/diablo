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
	adapter.runtime_transition_generation_.store(0, std::memory_order_release);
	adapter.audio_callbacks_inflight_.store(0, std::memory_order_release);
	Check(adapter.BeginAudioCallback(), "audio callback did not acquire a stable runtime generation");
	Check(!adapter.BeginRuntimeTransition(), "recovery entered while an audio callback held the runtime");
	adapter.audio_callbacks_inflight_.fetch_sub(1, std::memory_order_release);
	Check(adapter.BeginRuntimeTransition(), "recovery did not acquire the transition gate");
	Check(!adapter.BeginAudioCallback(), "audio callback entered during a runtime transition");
	adapter.EndRuntimeTransition();
	Check(adapter.BeginAudioCallback(), "audio callback did not resume after a runtime transition");
	adapter.audio_callbacks_inflight_.fetch_sub(1, std::memory_order_release);

	// A core reload resets every ABI frame slot. Adapter-side command shadows
	// must be discarded with that epoch or the next changed-run submission could
	// omit pixels that no longer exist in the freshly cleared slot.
	adapter.command_shadow_valid_.fill(true);
	adapter.command_next_slot_ = 2;
	adapter.command_attempt_fence_ = 99;
	adapter.command_submission_.active = true;
	adapter.command_scene_faulted_ = true;
	adapter.ResetCommandSceneState();
	Check(!adapter.command_shadow_valid_[0] && !adapter.command_shadow_valid_[1]
	          && !adapter.command_shadow_valid_[2]
	          && adapter.command_next_slot_ == 0 && adapter.command_attempt_fence_ == 1
	          && !adapter.command_submission_.active && !adapter.command_scene_faulted_,
	      "command scene state was not reset with the transport epoch");

	// PS/2 bit 1 means right mouse, but SDL motion uses SDL_BUTTON_RMASK (4),
	// not the raw PS/2 mask (2).
	adapter.ResetInputState();
	ClearEvents();
	adapter.PushMouse(Mouse(0x2, 3, -2));
	auto events = Events();
	Check(events.size() == 2, "right-mouse packet did not publish motion and edge");
	Check(events[0].type == SDL_MOUSEMOTION && events[0].motion.state == SDL_BUTTON_RMASK,
	      "motion did not translate the PS/2 right-button mask");
	Check(events[1].type == SDL_MOUSEBUTTONDOWN && events[1].button.button == SDL_BUTTON_RIGHT,
	      "right-button edge was not translated");

	// Extreme signed deltas must clamp without overflowing the cursor addition.
	adapter.ResetInputState();
	adapter.mouse_x_ = 0;
	adapter.mouse_y_ = 0;
	ClearEvents();
	adapter.PushMouse(Mouse(0, std::numeric_limits<std::int32_t>::max(),
	                        std::numeric_limits<std::int32_t>::min()));
	Check(adapter.mouse_x_ == static_cast<std::int32_t>(diablo::mister::transport::FRAME_WIDTH - 1U)
	          && adapter.mouse_y_ == 0,
	      "extreme mouse deltas did not clamp safely");
	ClearEvents();

	// OSD focus loss releases delivered state and forces a neutral/repress cycle.
	adapter.ResetInputState();
	ClearEvents();
	adapter.PushKeyboard(Keyboard(0x1d, true)); // W
	Check(Events().size() == 1, "initial keyboard press was not delivered");
	adapter.PushFocus(false);
	events = Events();
	Check(events.size() == 2 && events[0].type == SDL_WINDOWEVENT
	          && events[0].window.event == SDL_WINDOWEVENT_FOCUS_LOST
	          && events[1].type == SDL_KEYUP,
	      "focus loss did not publish an ordered release");
	adapter.PushFocus(true);
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_WINDOWEVENT
	          && events[0].window.event == SDL_WINDOWEVENT_FOCUS_GAINED,
	      "focus gain did not publish focus only");
	adapter.PushKeyboard(Keyboard(0x1d, false));
	Check(Events().empty(), "release after focus gain should only arm a future repress");
	adapter.PushKeyboard(Keyboard(0x1d, true));
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_KEYDOWN,
	      "key did not require neutral then re-press after focus gain");

	// SDL filtering must leave the desired state pending until a later reconcile
	// can queue the actual engine event.
	adapter.ResetInputState();
	ClearEvents();
	SDL_SetEventFilter(FilterKeyboardDown, nullptr);
	adapter.PushKeyboard(Keyboard(0x1d, true));
	Check(!adapter.keyboard_delivered_[SDL_SCANCODE_W], "filtered key was marked delivered");
	SDL_SetEventFilter(nullptr, nullptr);
	adapter.ReconcileInputState();
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_KEYDOWN
	          && adapter.keyboard_delivered_[SDL_SCANCODE_W],
	      "filtered key was not recovered by bounded reconciliation");

	// A physical keyboard and controller can hold the same engine key. Releasing
	// one source must not prematurely release the shared delivered key.
	adapter.ResetInputState();
	ClearEvents();
	adapter.PushKeyboard(Keyboard(0x11, true)); // left Alt
	adapter.PushJoystick(Joystick(1U << 4));    // maps to left Alt too
	ClearEvents();
	adapter.PushKeyboard(Keyboard(0x11, false));
	Check(adapter.KeyWanted(SDL_SCANCODE_LALT), "controller state did not retain shared left Alt");
	events = Events();
	Check(events.empty(), "shared keyboard/controller key was released too early");
	adapter.PushJoystick(Joystick(0));
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_KEYUP,
	      "shared key stayed delivered after every source released it");

	// Text is emitted only while SDL has text input active, using the aggregate
	// physical modifier state. Controller modifiers do not affect typed text.
	adapter.ResetInputState();
	ClearEvents();
	SDL_StartTextInput();
	adapter.PushKeyboard(Keyboard(0x12, true)); // left Shift
	adapter.PushKeyboard(Keyboard(0x1c, true)); // A
	events = Events();
	Check(events.size() == 3 && events[0].type == SDL_KEYDOWN && events[1].type == SDL_KEYDOWN
	          && (events[1].key.keysym.mod & KMOD_SHIFT) != 0 && events[2].type == SDL_TEXTINPUT
	          && std::strcmp(events[2].text.text, "A") == 0,
	      "shifted text input did not follow physical modifier state");
	SDL_StopTextInput();

	// A queued keydown does not prove that the paired text event reached the
	// engine. Keep the character pending when SDL filters it, then deliver it
	// exactly once after the filter is removed.
	adapter.ResetInputState();
	ClearEvents();
	SDL_StartTextInput();
	SDL_SetEventFilter(FilterTextInput, nullptr);
	adapter.PushKeyboard(Keyboard(0x1c, true)); // A
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_KEYDOWN
	          && adapter.text_pending_[SDL_SCANCODE_A],
	      "filtered text input was not retained after its keydown");
	SDL_SetEventFilter(nullptr, nullptr);
	adapter.ReconcileInputState();
	events = Events();
	Check(events.size() == 1 && events[0].type == SDL_TEXTINPUT
	          && std::strcmp(events[0].text.text, "a") == 0
	          && !adapter.text_pending_[SDL_SCANCODE_A],
	      "pending text input was not recovered exactly once");
	adapter.PushKeyboard(Keyboard(0x1c, false));
	Check(Events().size() == 1, "key release after recovered text was not delivered");
	SDL_StopTextInput();

	SDL_Quit();
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
		adapter.ResetProfile();
		const auto start = adapter.NowNs();
		Check(start != 0, "monotonic clock was unavailable for profile accounting");
		adapter.RecordProfile(start, false, true, Adapter::ProfileOutcome::PublishFailed);
		Check(adapter.profile_present_count_ == 1, "failed presentation was not counted");
		Check(adapter.profile_published_count_ == 0, "failed presentation was counted as published");
		Check(adapter.profile_backpressure_count_ == 1, "backpressure was not retained on publish failure");
		Check(adapter.profile_outcome_counts_[static_cast<std::size_t>(Adapter::ProfileOutcome::PublishFailed)] == 1,
		      "publish-failure outcome was not counted");
		adapter.RecordProfile(0, false, false, Adapter::ProfileOutcome::RuntimeUnavailable);
		Check(adapter.profile_present_count_ == 2 && adapter.profile_timing_invalid_count_ == 1,
		      "invalid monotonic sample was not retained as an outcome");
		Check(adapter.EmitProfileTrace(), "profile trace write unexpectedly failed");
		Check(!adapter.profile_trace_write_failed_, "successful profile trace was marked failed");
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
		Check(!adapter.EmitProfileTrace() && adapter.profile_trace_write_failed_,
		      "profile trace silently replaced an existing evidence path");
		std::remove("transport-profile-trace-test.jsonl");
		adapter.ResetProfile();
		for (std::size_t index = 0; index < Adapter::kProfileTraceCapacity + 2; ++index)
			adapter.RecordProfile(start, false, false, Adapter::ProfileOutcome::BackpressureDropped);
		Check(adapter.profile_trace_count_ == Adapter::kProfileTraceCapacity
		          && adapter.profile_trace_dropped_ == 2,
		      "bounded trace did not count overwritten telemetry records");
		Check(adapter.EmitProfileTrace(), "overflow profile trace write unexpectedly failed");
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
