# Loading uses real SDL events for thread completion and window management.
# During playback, live mouse input must not overwrite recorded cursor/button
# state. Keep recorded events in interface_msg_pump and ordinary play unchanged.
diablo_host_patch_file(interfac.cpp
  8503b4d3acb2173b29d3171eadba721821f6a8b3de20849eca0b2e6385c5017a
  [[			HandleMessage(event, modState);]]
  [[            if (demo::IsRunning()
                && (event.type == SDL_MOUSEMOTION
                    || event.type == SDL_MOUSEBUTTONDOWN
                    || event.type == SDL_MOUSEBUTTONUP)) {
                continue;
            }
			HandleMessage(event, modState);]]
  "${overlay}/interfac.cpp")
set(output "${overlay}/interfac.cpp")
file(READ "${output}" content)
file(CONFIGURE OUTPUT "${output}" CONTENT "#include \"engine/demomode.h\"\n${content}" @ONLY NEWLINE_STYLE UNIX)
file(SHA256 "${output}" final_hash)
file(APPEND "${CMAKE_BINARY_DIR}/host-engine-fixes.txt" "replay-loading interfac.cpp ${final_hash}\n")
get_target_property(engine_sources libdevilutionx SOURCES)
list(REMOVE_ITEM engine_sources "interfac.cpp" "${PROJECT_SOURCE_DIR}/Source/interfac.cpp")
list(APPEND engine_sources "${output}")
set_property(TARGET libdevilutionx PROPERTY SOURCES "${engine_sources}")
