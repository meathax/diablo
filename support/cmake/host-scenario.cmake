# Explicitly enabled native-resolution smoke scenario; ordinary runs are unchanged.
diablo_host_patch_file(menu.cpp
  035dda9176d388d69a24a97339a547a7e08d9b39bb65412bacc0547dce327944
  [[		gbLoadGame = true;]]
  [[		gbLoadGame = true;
        diablo_reference::BeginNativeScenario();]]
  "${overlay}/menu.cpp")
diablo_host_patch_file(engine/demomode.cpp
  31b6bff3375921ba5c93bd1f9636bf1595bc97cee0223d2043886ce3a9a348a8
  [[void NotifyGameLoopEnd()
{]]
  [[void NotifyGameLoopEnd()
{
    diablo_reference::FinishNativeScenario(LogicTick);]]
  "${overlay}/engine/demomode.cpp")
file(READ "${overlay}/engine/demomode.cpp" demomode_content)
set(scenario_tick_before [[if (isGameTick)
		LogicTick++;]])
set(scenario_tick_after [[if (isGameTick) {
		LogicTick++;
		diablo_reference::NativeScenarioTick(LogicTick);
	}]])
string(FIND "${demomode_content}" "${scenario_tick_before}" scenario_tick_site)
if(scenario_tick_site LESS 0)
  # DevilutionX 1.5.5 names the same hook by demo message type.
  set(scenario_tick_before [[if (dmsg.type == DemoMsgType::GameTick)
		LogicTick++;]])
  set(scenario_tick_after [[if (dmsg.type == DemoMsgType::GameTick) {
		LogicTick++;
		diablo_reference::NativeScenarioTick(LogicTick);
	}]])
  string(FIND "${demomode_content}" "${scenario_tick_before}" scenario_tick_site)
endif()
if(scenario_tick_site LESS 0)
  message(FATAL_ERROR "Pinned replay tick hook site is missing")
endif()
string(REPLACE "${scenario_tick_before}" "${scenario_tick_after}" demomode_content "${demomode_content}")
foreach(required_hook "FinishNativeScenario(LogicTick)" "NativeScenarioTick(LogicTick)")
  string(FIND "${demomode_content}" "${required_hook}" hook_position)
  if(hook_position LESS 0)
    message(FATAL_ERROR "Scenario overlay lost ${required_hook}")
  endif()
endforeach()
file(CONFIGURE OUTPUT "${overlay}/engine/demomode.cpp" CONTENT "${demomode_content}" @ONLY NEWLINE_STYLE UNIX)
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
