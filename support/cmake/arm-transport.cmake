# ARM target overlay for the MiSTer transport boundary. The pinned engine
# checkout remains unchanged; CMake builds generated copies of the affected
# translation units and records the source hash that admitted each patch.
if(NOT CMAKE_SYSTEM_PROCESSOR STREQUAL "armv7")
  message(FATAL_ERROR "MiSTer transport overlay requires the ARMv7 toolchain")
endif()

set(_mister_reference_dir "${CMAKE_CURRENT_LIST_DIR}/../reference")
set(_mister_overlay_dir "${CMAKE_BINARY_DIR}/mister-engine-overlay")
set(_mister_svid_expected_sha256 "6e6aa7f4d360c2e3c23206c62342bc008f7b7551d3816c9f217b05182db7e715")

function(diablo_mister_transport)
  file(MAKE_DIRECTORY "${_mister_overlay_dir}/engine")
  file(WRITE "${CMAKE_BINARY_DIR}/mister-transport-fixes.txt"
    "MiSTer transport overlays; original checkout unchanged.\n")

  set(dx_source "${PROJECT_SOURCE_DIR}/Source/engine/dx.cpp")
  file(SHA256 "${dx_source}" dx_observed)
  if(NOT dx_observed STREQUAL "923338e58ba57b612f1ba4bccc6584e2b194d92fe0a1efc164955ea159a457ab")
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
  string(REPLACE
    [[	SDL_Surface *surface = GetOutputSurface();
]]
    [[	SDL_Surface *surface = GetOutputSurface();

	if (::diablo::mister::sdl::Active()
	    && ::diablo::mister::sdl::Present(PalSurface, static_cast<std::uint64_t>(SDL_GetTicks()))) {
		if (::diablo::mister::sdl::CpuPacingEnabled()) {
			if (::diablo::mister::sdl::ForceFramePacing())
				::diablo::mister::sdl::PaceFrame();
			else
				LimitFrameRate();
		}
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
  if(NOT sound_observed STREQUAL "32e84d454ebb46bb696c7dc304b45406c1e5c95045c40e0122734c22a53b0e4e")
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
  get_target_property(sound_sources libdevilutionx_sound SOURCES)
  list(REMOVE_ITEM sound_sources engine/sound.cpp "${sound_source}")
  list(APPEND sound_sources "${sound_output}")
  set_property(TARGET libdevilutionx_sound PROPERTY SOURCES "${sound_sources}")
  set_property(SOURCE "${sound_output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
    APPEND PROPERTY INCLUDE_DIRECTORIES "${_mister_reference_dir}")
  # The upstream sound object library is linked into libdevilutionx. Remove any
  # stale overlay entry left by an earlier configure before replacing its source
  # in the owning object library above.
  get_target_property(monolithic_sources libdevilutionx SOURCES)
  list(REMOVE_ITEM monolithic_sources "${sound_output}" "engine/sound.cpp" "${sound_source}")
  set_property(TARGET libdevilutionx PROPERTY SOURCES "${monolithic_sources}")
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
    [[    Aulib::Stream_priv::fSdlCallbackImpl(nullptr, out, outLen);
    ::diablo::mister::sdl::PublishPcmBytes(out, static_cast<std::size_t>(outLen));]]
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
  if(NOT main_observed STREQUAL "dffc9d98ff32d8cd93547cebf0394617e8d345d3a88673f5c1c8f3965407ea48")
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
  # MiSTer joystick records are translated to deterministic SDL keyboard
  # events by the transport adapter. Enable DevilutionX's keyboard-controller
  # path so the same events drive controller-only actions in menus and gameplay.
  set(_mister_controller_definitions
    HAS_KBCTRL=1
    KBCTRL_BUTTON_DPAD_LEFT=SDLK_LEFT
    KBCTRL_BUTTON_DPAD_RIGHT=SDLK_RIGHT
    KBCTRL_BUTTON_DPAD_UP=SDLK_UP
    KBCTRL_BUTTON_DPAD_DOWN=SDLK_DOWN
    KBCTRL_BUTTON_A=SDLK_LALT
    KBCTRL_BUTTON_B=SDLK_LCTRL
    KBCTRL_BUTTON_X=SDLK_LSHIFT
    KBCTRL_BUTTON_Y=SDLK_SPACE
    KBCTRL_BUTTON_LEFTSHOULDER=SDLK_TAB
    KBCTRL_BUTTON_RIGHTSHOULDER=SDLK_BACKSPACE
    KBCTRL_BUTTON_TRIGGERLEFT=SDLK_PAGEUP
    KBCTRL_BUTTON_TRIGGERRIGHT=SDLK_PAGEDOWN
    KBCTRL_BUTTON_LEFTSTICK=SDLK_HOME
    KBCTRL_BUTTON_RIGHTSTICK=SDLK_END
    KBCTRL_BUTTON_START=SDLK_RETURN
    KBCTRL_BUTTON_BACK=SDLK_ESCAPE)
  target_compile_definitions(devilutionx PRIVATE
    DIABLO_MISTER_TRANSPORT_TARGET=1 ${_mister_controller_definitions})
  target_compile_definitions(libdevilutionx PRIVATE ${_mister_controller_definitions})
  include("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/mister-controller.cmake")
endfunction()

cmake_language(DEFER CALL diablo_mister_transport)
