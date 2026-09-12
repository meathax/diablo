# Include from the deferred host integration after engine targets are defined.
# Used only by the Windows host reference; capture is dormant without its env flag.
set(capture_source "${PROJECT_SOURCE_DIR}/Source/engine/render/scrollrt.cpp")
file(SHA256 "${capture_source}" observed)
if(NOT observed STREQUAL "df6b5e704bf92ca677899397d214a118a642dbe3f7069016e07f8207fd055f6a")
  message(FATAL_ERROR "Unexpected scrollrt.cpp input for reference capture")
endif()
file(READ "${capture_source}" capture_content)
string(REPLACE "\r\n" "\n" capture_content "${capture_content}")
string(REPLACE [[#include "engine/render/scrollrt.h"]]
  [[#include "engine/render/scrollrt.h"
#include "host_capture.hpp"
#include "engine/demomode.h"]] capture_content "${capture_content}")
string(REPLACE [[	RenderPresent();
}

} // namespace devilution]]
  [[    diablo_reference::CaptureRenderedFrame(out, SDL_GetTicks());
	RenderPresent();
}

} // namespace devilution]] capture_content "${capture_content}")
set(capture_output "${CMAKE_BINARY_DIR}/host-engine-overlay/engine/render/scrollrt.cpp")
file(CONFIGURE OUTPUT "${capture_output}" CONTENT "${capture_content}" @ONLY NEWLINE_STYLE UNIX)
get_target_property(engine_sources libdevilutionx SOURCES)
list(REMOVE_ITEM engine_sources engine/render/scrollrt.cpp "${capture_source}")
list(APPEND engine_sources "${capture_output}")
set_property(TARGET libdevilutionx PROPERTY SOURCES "${engine_sources}")
set_property(SOURCE "${capture_output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
  APPEND PROPERTY INCLUDE_DIRECTORIES "${CMAKE_CURRENT_LIST_DIR}/../reference")
file(SHA256 "${capture_output}" patched)
file(APPEND "${CMAKE_BINARY_DIR}/host-engine-fixes.txt" "engine/render/scrollrt.cpp ${observed} ${patched}\n")
