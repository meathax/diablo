# Loading uses real SDL events for thread completion and window management.
# During playback, live mouse input must not overwrite recorded cursor/button
# state. Keep recorded events in interface_msg_pump and ordinary play unchanged.
diablo_host_patch_file(interfac.cpp
  32a11d0891c5d23a470690e214a28d928a8a4a49db14c99a68ddc03913fe10a0
  [[			HandleMessage(event, SDL_GetModState());]]
  [[            if (demo::IsRunning()
                && (event.type == SDL_EVENT_MOUSE_MOTION
                    || event.type == SDL_EVENT_MOUSE_BUTTON_DOWN
                    || event.type == SDL_EVENT_MOUSE_BUTTON_UP)) {
                continue;
            }
			HandleMessage(event, SDL_GetModState());]]
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
