# ARM target overlay for the MiSTer transport boundary. The pinned engine
# checkout remains unchanged; CMake builds generated copies of the affected
# translation units and records the source hash that admitted each patch.
if(NOT CMAKE_SYSTEM_PROCESSOR STREQUAL "armv7")
  message(FATAL_ERROR "MiSTer transport overlay requires the ARMv7 toolchain")
endif()

# The MiSTer release supports Diablo/Hellfire plus the native DevilutionX
# multiplayer transports.
set(NONET OFF CACHE BOOL "Disable network support for MiSTer" FORCE)
set(DISABLE_TCP OFF CACHE BOOL "Disable TCP multiplayer for MiSTer" FORCE)
set(DISABLE_ZERO_TIER OFF CACHE BOOL "Disable ZeroTier multiplayer for MiSTer" FORCE)
# MiSTer must keep DevilutionX alive when the in-game Quit Game action is
# selected so it can return to the title menu instead of leaving the resident
# handler on a black frame after the SDL process exits.
set(NOEXIT ON CACHE BOOL "Return to the title menu instead of exiting" FORCE)

set(_mister_reference_dir "${CMAKE_CURRENT_LIST_DIR}/../reference")
set(_mister_overlay_dir "${CMAKE_BINARY_DIR}/mister-engine-overlay")
  set(_mister_svid_expected_sha256 "73626c3cbf7d99386c2e84a9f4e57b4b894fa66ab2f9efe20c1c4ab52eeb2d60")

function(diablo_mister_transport)
  file(MAKE_DIRECTORY "${_mister_overlay_dir}/engine")
  file(WRITE "${CMAKE_BINARY_DIR}/mister-transport-fixes.txt"
    "MiSTer transport overlays; original checkout unchanged.\n")

  target_include_directories(libdevilutionx PRIVATE "${_mister_reference_dir}")

  # SDL's dummy video driver can report text input as inactive on MiSTer even
  # after the native UI starts an editable field. Mirror UiEdit ownership in a
  # hint consumed by the transport input bridge so only text-entry screens get
  # the synthetic SDL_TEXTINPUT event.
  set(ui_source "${PROJECT_SOURCE_DIR}/Source/DiabloUI/diabloui.cpp")
  file(SHA256 "${ui_source}" ui_observed)
  if(NOT ui_observed STREQUAL "38fe000e7d054a69a047deb1284877a5d0da9e0c1d06e20527ee4b6aaec3c7b5")
    message(FATAL_ERROR "Unexpected pinned diabloui.cpp input for MiSTer text input")
  endif()
  file(READ "${ui_source}" ui_content)
  string(REPLACE
    [[	SDL_StopTextInput(); // input is enabled by default
#endif]]
    [[	SDL_StopTextInput(); // input is enabled by default
	SDL_SetHint("DIABLO_MISTER_TEXT_INPUT_ACTIVE", "0");
#endif]]
    ui_content "${ui_content}")
  string(REPLACE
    [[			UiTextInputState.emplace(TextInputState::Options {
			    .value = pItemUIEdit->m_value,
			    .cursor = &pItemUIEdit->m_cursor,
			    .maxLength = pItemUIEdit->m_max_length,
			});]]
    [[			UiTextInputState.emplace(TextInputState::Options {
			    .value = pItemUIEdit->m_value,
			    .cursor = &pItemUIEdit->m_cursor,
			    .maxLength = pItemUIEdit->m_max_length,
			});
			SDL_SetHint("DIABLO_MISTER_TEXT_INPUT_ACTIVE", "1");]]
    ui_content "${ui_content}")
  string(REPLACE
    [[void UiInitList_clear()
{
	SelectedItem = 0;]]
    [[void UiInitList_clear()
{
	SDL_SetHint("DIABLO_MISTER_TEXT_INPUT_ACTIVE", "0");
	SelectedItem = 0;]]
    ui_content "${ui_content}")
  string(REPLACE
    [[		SDL_StopTextInput();
#endif
		UiTextInputState = std::nullopt;]]
    [[		SDL_StopTextInput();
		SDL_SetHint("DIABLO_MISTER_TEXT_INPUT_ACTIVE", "0");
#endif
		UiTextInputState = std::nullopt;]]
    ui_content "${ui_content}")
  set(ui_output "${_mister_overlay_dir}/diabloui.cpp")
  file(CONFIGURE OUTPUT "${ui_output}" CONTENT "${ui_content}" @ONLY NEWLINE_STYLE UNIX)
  file(SHA256 "${ui_output}" ui_patched)
  file(APPEND "${CMAKE_BINARY_DIR}/mister-transport-fixes.txt"
    "DiabloUI/diabloui.cpp ${ui_observed} ${ui_patched}\n")
  get_target_property(ui_sources libdevilutionx SOURCES)
  list(REMOVE_ITEM ui_sources DiabloUI/diabloui.cpp "${ui_source}")
  list(APPEND ui_sources "${ui_output}")
  set_property(TARGET libdevilutionx PROPERTY SOURCES "${ui_sources}")
  set_property(SOURCE "${ui_output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
    APPEND PROPERTY INCLUDE_DIRECTORIES "${_mister_reference_dir}")

  # NONET disables networking but upstream still exposes the multiplayer menu.
  set(menu_source "${PROJECT_SOURCE_DIR}/Source/DiabloUI/mainmenu.cpp")
  file(READ "${menu_source}" menu_content)
  set(multiplayer_item [[vecMenuItems.push_back(std::make_unique<UiListItem>(_("Multi Player"), MAINMENU_MULTIPLAYER));]])
  string(FIND "${menu_content}" "${multiplayer_item}" multiplayer_position)
  if(multiplayer_position EQUAL -1)
    message(FATAL_ERROR "Unexpected mainmenu.cpp: multiplayer item not found")
  endif()
  if(NONET)
    string(REPLACE "${multiplayer_item}" "// Multiplayer is disabled in the MiSTer release." menu_content "${menu_content}")
  endif()
  set(menu_output "${_mister_overlay_dir}/mainmenu.cpp")
  file(CONFIGURE OUTPUT "${menu_output}" CONTENT "${menu_content}" @ONLY NEWLINE_STYLE UNIX)
  file(SHA256 "${menu_source}" menu_observed)
  file(SHA256 "${menu_output}" menu_patched)
  file(APPEND "${CMAKE_BINARY_DIR}/mister-transport-fixes.txt"
    "DiabloUI/mainmenu.cpp ${menu_observed} ${menu_patched}\n")
  get_target_property(menu_sources libdevilutionx SOURCES)
  list(REMOVE_ITEM menu_sources DiabloUI/mainmenu.cpp "${menu_source}")
  list(APPEND menu_sources "${menu_output}")
  set_property(TARGET libdevilutionx PROPERTY SOURCES "${menu_sources}")

  set(dx_source "${PROJECT_SOURCE_DIR}/Source/engine/dx.cpp")
  file(SHA256 "${dx_source}" dx_observed)
  if(NOT dx_observed STREQUAL "04f25f495210dfa631b78747d6d80c11554bf976ddcc22523abf2833ef7ed30e")
    message(FATAL_ERROR "Unexpected pinned dx.cpp input for MiSTer transport")
  endif()
  file(READ "${dx_source}" dx_content)
  string(REPLACE
    [[#include "engine/dx.h"]]
    [[#include "engine/dx.h"
#include "mister_transport_sdl.hpp"]]
    dx_content "${dx_content}")
  string(REPLACE
    [[	CreateBackBuffer();
}]]
    [[	CreateBackBuffer();
	::diablo::mister::sdl::Initialize();
}]]
    dx_content "${dx_content}")
  string(REPLACE
    [[	PalSurface = nullptr;
	PinnedPalSurface = nullptr;]]
	[[	::diablo::mister::sdl::Shutdown();
	PalSurface = nullptr;
	PinnedPalSurface = nullptr;]]
    dx_content "${dx_content}")
  # FPGA consumes PalSurface directly. Upstream's screen blit otherwise expands
  # its indexed pixels into an unused SDL output surface on every dirty region.
  string(REPLACE
    [[void BltFast(SDL_Rect *srcRect, SDL_Rect *dstRect)
{]]
    [[void BltFast(SDL_Rect *srcRect, SDL_Rect *dstRect)
{
	if (::diablo::mister::sdl::Active())
		return;]]
    dx_content "${dx_content}")
  string(REPLACE
    [[	SDL_Surface *surface = GetOutputSurface();
]]
    [[	SDL_Surface *surface = GetOutputSurface();

	if (::diablo::mister::sdl::Active()) {
		if (::diablo::mister::sdl::CpuPacingEnabled())
			::diablo::mister::sdl::PaceFrame();
		(void)::diablo::mister::sdl::Present(PalSurface, static_cast<std::uint64_t>(SDL_GetTicks()));
		// No conversion/blit to the dummy SDL display when the FPGA queue is full.
		return;
	}
]]
    dx_content "${dx_content}")
  set(dx_output "${_mister_overlay_dir}/engine/dx.cpp")
  file(CONFIGURE OUTPUT "${dx_output}" CONTENT "${dx_content}" @ONLY NEWLINE_STYLE UNIX)
  file(SHA256 "${dx_output}" dx_patched)
  file(APPEND "${CMAKE_BINARY_DIR}/mister-transport-fixes.txt"
    "engine/dx.cpp ${dx_observed} ${dx_patched}\n")
  get_target_property(engine_sources libdevilutionx SOURCES)
  list(REMOVE_ITEM engine_sources engine/dx.cpp "${dx_source}")
  list(APPEND engine_sources "${dx_output}")
  set_property(TARGET libdevilutionx PROPERTY SOURCES "${engine_sources}")
  set_property(SOURCE "${dx_output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
    APPEND PROPERTY INCLUDE_DIRECTORIES "${_mister_reference_dir}")

  set(svid_source "${PROJECT_SOURCE_DIR}/Source/storm/storm_svid.cpp")
  file(SHA256 "${svid_source}" svid_observed)
  if(NOT svid_observed STREQUAL "${_mister_svid_expected_sha256}")
    message(FATAL_ERROR "Unexpected pinned storm_svid.cpp input for MiSTer transport")
  endif()
  file(READ "${svid_source}" svid_content)
  set(svid_prefix "#include <cstdint>\n#include <cstdio>\n#include \"mister_movie_frame.hpp\"\n#include \"mister_transport_sdl.hpp\"\n")
  set(svid_content "${svid_prefix}${svid_content}")
  set(svid_marker [[bool BlitFrame()
{
]])
  set(svid_hook [[bool BlitFrame()
{
  if (::diablo::mister::sdl::Active()) {
    static ::diablo::mister::movie::IndexedFrameAdapter movie_frame;
    const auto prepared = movie_frame.Prepare(SVidSurface.get());
    if (prepared.surface == nullptr) {
      if (movie_frame.ConsumeErrorNotice()) {
        std::fprintf(stderr, "Diablo MiSTer cinematic surface rejected: error=%d sdl=%s\n",
          static_cast<int>(prepared.error), SDL_GetError());
      }
      return true;
    }
    if (movie_frame.ConsumeApproximateBorderNotice(prepared.approximate_border)) {
      std::fputs("Diablo MiSTer cinematic letterbox uses nearest palette color for black\n", stderr);
    }
    (void)::diablo::mister::sdl::Present(prepared.surface, static_cast<std::uint64_t>(SDL_GetTicks()));
    return true;
  }
]])
  string(FIND "${svid_content}" "${svid_marker}" svid_marker_at)
  if(svid_marker_at EQUAL -1)
    message(FATAL_ERROR "storm_svid.cpp BlitFrame identity marker not found")
  endif()
  string(REPLACE "${svid_marker}" "${svid_hook}" svid_content "${svid_content}")
  set(svid_output "${_mister_overlay_dir}/storm_svid.cpp")
  file(CONFIGURE OUTPUT "${svid_output}" CONTENT "${svid_content}" @ONLY NEWLINE_STYLE UNIX)
  file(SHA256 "${svid_output}" svid_patched)
  file(APPEND "${CMAKE_BINARY_DIR}/mister-transport-fixes.txt"
    "storm/storm_svid.cpp ${svid_observed} ${svid_patched}\n")
  get_target_property(svid_sources libdevilutionx SOURCES)
  list(REMOVE_ITEM svid_sources storm/storm_svid.cpp "${svid_source}")
  list(APPEND svid_sources "${svid_output}")
  set_property(TARGET libdevilutionx PROPERTY SOURCES "${svid_sources}")
  set_property(SOURCE "${svid_output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
    APPEND PROPERTY INCLUDE_DIRECTORIES "${_mister_reference_dir}")

  set(sound_source "${PROJECT_SOURCE_DIR}/Source/engine/sound.cpp")
  file(SHA256 "${sound_source}" sound_observed)
  if(NOT sound_observed STREQUAL "3a864798410355fecda39d5648fdd07ae59027803807e9cc1ba96fee7d46328e")
    message(FATAL_ERROR "Unexpected pinned sound.cpp input for MiSTer transport")
  endif()
  file(READ "${sound_source}" sound_content)
  string(REPLACE
    [[#include "engine/sound.h"]]
    [[#include "engine/sound.h"
#include "mister_transport_sdl.hpp"]]
    sound_content "${sound_content}")
  string(REPLACE
    [[	specHint.freq = static_cast<int>(*audioOptions.sampleRate);]]
    [[	specHint.freq = ::diablo::mister::sdl::Requested()
	    ? 22050
	    : static_cast<int>(*audioOptions.sampleRate);]]
    sound_content "${sound_content}")
  string(REPLACE
    [[	if (!Aulib::init(*GetOptions().Audio.sampleRate, AUDIO_S16, *GetOptions().Audio.channels, *GetOptions().Audio.bufferSize, *GetOptions().Audio.device)) {]]
    [[	const int transport_sample_rate = ::diablo::mister::sdl::Requested()
	    ? 22050
	    : static_cast<int>(*GetOptions().Audio.sampleRate);
	const int transport_channels = ::diablo::mister::sdl::Requested()
	    ? 2
	    : static_cast<int>(*GetOptions().Audio.channels);
	// Keep callbacks large enough to avoid starving the SDL audio thread on the
	// ARM target while the framebuffer is being copied.  The FPGA-side FIFO
	// absorbs the resulting bounded chunk latency.
	const int transport_buffer_size = ::diablo::mister::sdl::Requested()
	    ? 1024
	    : static_cast<int>(*GetOptions().Audio.bufferSize);
	if (!Aulib::init(transport_sample_rate, AUDIO_S16, transport_channels, transport_buffer_size, *GetOptions().Audio.device)) {]]
    sound_content "${sound_content}")
  string(REPLACE
    [[	specHint.channels = *audioOptions.channels;]]
    [[	specHint.channels = ::diablo::mister::sdl::Requested()
	    ? 2
	    : *audioOptions.channels;]]
    sound_content "${sound_content}")
  set(sound_output "${_mister_overlay_dir}/engine/sound.cpp")
  file(CONFIGURE OUTPUT "${sound_output}" CONTENT "${sound_content}" @ONLY NEWLINE_STYLE UNIX)
  file(SHA256 "${sound_output}" sound_patched)
  file(APPEND "${CMAKE_BINARY_DIR}/mister-transport-fixes.txt"
    "engine/sound.cpp ${sound_observed} ${sound_patched}\n")
  if(TARGET libdevilutionx_sound)
    get_target_property(sound_sources libdevilutionx_sound SOURCES)
    list(REMOVE_ITEM sound_sources engine/sound.cpp "${sound_source}")
    list(APPEND sound_sources "${sound_output}")
    set_property(TARGET libdevilutionx_sound PROPERTY SOURCES "${sound_sources}")
  else()
    # DevilutionX 1.5.5 keeps engine/sound.cpp in the monolithic engine target.
    get_target_property(monolithic_sound_sources libdevilutionx SOURCES)
    list(REMOVE_ITEM monolithic_sound_sources engine/sound.cpp "${sound_source}")
    list(APPEND monolithic_sound_sources "${sound_output}")
    set_property(TARGET libdevilutionx PROPERTY SOURCES "${monolithic_sound_sources}")
  endif()
  set_property(SOURCE "${sound_output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
    APPEND PROPERTY INCLUDE_DIRECTORIES "${_mister_reference_dir}")
  # The upstream sound object library is linked into libdevilutionx. Remove any
  # stale overlay entry left by an earlier configure before replacing its source
  # in the owning object library above.
  if(TARGET libdevilutionx_sound)
    get_target_property(monolithic_sources libdevilutionx SOURCES)
    list(REMOVE_ITEM monolithic_sources "${sound_output}" "engine/sound.cpp" "${sound_source}")
    set_property(TARGET libdevilutionx PROPERTY SOURCES "${monolithic_sources}")
  endif()
  target_sources(libdevilutionx PRIVATE
    "${_mister_reference_dir}/mister_transport_audio.cpp")
  target_include_directories(libdevilutionx PRIVATE "${_mister_reference_dir}")

  if(NOT TARGET SDL_audiolib)
    message(FATAL_ERROR "SDL_audiolib target is required for MiSTer PCM transport")
  endif()
  set(aulib_source "${SDL_audiolib_SOURCE_DIR}/src/aulib.cpp")
  file(SHA256 "${aulib_source}" aulib_observed)
  if(NOT aulib_observed STREQUAL "eb4eda01ce58b542a1d94cd9098a9b1c58dd9d0868e2705092b7531b7e539892")
    message(FATAL_ERROR "Unexpected pinned aulib.cpp input for MiSTer transport")
  endif()
  file(READ "${aulib_source}" aulib_content)
  string(REPLACE
    [[#include "aulib.h"]]
    [[#include "aulib.h"
#include "mister_transport_audio.hpp"
#include <cstddef>]]
    aulib_content "${aulib_content}")
  string(REPLACE
    [[    Aulib::Stream_priv::fSdlCallbackImpl(nullptr, out, outLen);]]
    [[    if (!::diablo::mister::sdl::ServicePcmAudio(
            &Aulib::Stream_priv::fSdlCallbackImpl, nullptr, out, outLen))
        Aulib::Stream_priv::fSdlCallbackImpl(nullptr, out, outLen);]]
    aulib_content "${aulib_content}")
  set(aulib_output "${_mister_overlay_dir}/aulib.cpp")
  file(CONFIGURE OUTPUT "${aulib_output}" CONTENT "${aulib_content}" @ONLY NEWLINE_STYLE UNIX)
  file(SHA256 "${aulib_output}" aulib_patched)
  file(APPEND "${CMAKE_BINARY_DIR}/mister-transport-fixes.txt"
    "SDL_audiolib/src/aulib.cpp ${aulib_observed} ${aulib_patched}\n")
  get_target_property(aulib_sources SDL_audiolib SOURCES)
  list(REMOVE_ITEM aulib_sources src/aulib.cpp "${aulib_source}")
  list(APPEND aulib_sources "${aulib_output}")
  set_property(TARGET SDL_audiolib PROPERTY SOURCES "${aulib_sources}")
  set_property(SOURCE "${aulib_output}" DIRECTORY "${SDL_audiolib_SOURCE_DIR}"
    APPEND PROPERTY INCLUDE_DIRECTORIES "${_mister_reference_dir}")

  set(main_source "${PROJECT_SOURCE_DIR}/Source/main.cpp")
  file(SHA256 "${main_source}" main_observed)
  if(NOT main_observed STREQUAL "6f8d4e2d3b6287705a788a0ebb9f73f3a4981fd832549f2945b84143c2bcbf1c")
    message(FATAL_ERROR "Unexpected pinned main.cpp input for MiSTer transport")
  endif()
  set(main_output "${_mister_overlay_dir}/main.cpp")
  configure_file("${_mister_reference_dir}/mister_main.cpp" "${main_output}" COPYONLY)
  file(SHA256 "${main_output}" main_patched)
  file(APPEND "${CMAKE_BINARY_DIR}/mister-transport-fixes.txt"
    "main.cpp ${main_observed} ${main_patched}\n")
  get_target_property(binary_sources devilutionx SOURCES)
  list(REMOVE_ITEM binary_sources Source/main.cpp "${main_source}")
  list(APPEND binary_sources "${main_output}")
  set_property(TARGET devilutionx PROPERTY SOURCES "${binary_sources}")
  target_include_directories(devilutionx PRIVATE "${_mister_reference_dir}")

  # Transport controllers are registered SDL game controllers. Do not enable
  # keyboard-controller emulation: physical arrows/modifiers must remain keys.
  # The 1.5.5 project defaults to C++20, while the project-owned transport
  # boundary uses std::expected and therefore requires C++23.
  target_compile_features(libdevilutionx PRIVATE cxx_std_23)
  target_compile_features(devilutionx PRIVATE cxx_std_23)
  target_compile_definitions(devilutionx PRIVATE
    DIABLO_MISTER_TRANSPORT_TARGET=1)
  include("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/mister-controller.cmake")
  include("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/mister-controller-admission.cmake")
endfunction()

cmake_language(DEFER CALL diablo_mister_transport)

# Optional and independently guarded; incompatible or audio-only builds retain
# their existing renderer.
include("${CMAKE_CURRENT_LIST_DIR}/mister-lighting.cmake")
