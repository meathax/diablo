# Explicitly enabled native-resolution smoke scenario; ordinary runs are unchanged.
diablo_host_patch_file(menu.cpp
  fadac067f0b1283b82182fdc6be0ba1e03eaad24bc851e79db9256e8768d1f33
  [[		gbLoadGame = true;]]
  [[		gbLoadGame = true;
        diablo_reference::BeginNativeScenario(gameData);]]
  "${overlay}/menu.cpp")
diablo_host_patch_file(engine/demomode.cpp
  4f0daf1abb08551e5ad7c317fb27c9804baea708b9161d278b6effd7fb03344e
  [[void NotifyGameLoopEnd()
{]]
  [[void NotifyGameLoopEnd()
{
    diablo_reference::FinishNativeScenario(LogicTick);]]
  "${overlay}/engine/demomode.cpp")
foreach(relative menu.cpp engine/demomode.cpp)
  set(output "${overlay}/${relative}")
  file(READ "${output}" content)
  file(CONFIGURE OUTPUT "${output}" CONTENT "#include \"host_scenario.hpp\"\n${content}" @ONLY NEWLINE_STYLE UNIX)
  file(SHA256 "${output}" final_hash)
  file(APPEND "${CMAKE_BINARY_DIR}/host-engine-fixes.txt" "scenario-include ${relative} ${final_hash}\n")
  get_target_property(engine_sources libdevilutionx SOURCES)
  list(REMOVE_ITEM engine_sources "${relative}" "${PROJECT_SOURCE_DIR}/Source/${relative}")
  list(APPEND engine_sources "${output}")
  set_property(TARGET libdevilutionx PROPERTY SOURCES "${engine_sources}")
  set_property(SOURCE "${output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
    APPEND PROPERTY INCLUDE_DIRECTORIES "${CMAKE_CURRENT_LIST_DIR}/../reference")
endforeach()
