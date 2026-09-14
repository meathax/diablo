# Preserve the 1.5.5 wire protocol while serializing composed TCP writes.
include_guard(GLOBAL)
function(diablo_netplay_fixes)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  set(patcher "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../netplay_overlay.py")
  set(output "${CMAKE_BINARY_DIR}/netplay-overlay")
  execute_process(COMMAND "${Python3_EXECUTABLE}" "${patcher}"
    "${PROJECT_SOURCE_DIR}/Source/dvlnet" "${output}/dvlnet"
    RESULT_VARIABLE result OUTPUT_VARIABLE details ERROR_VARIABLE errors)
  if(NOT result EQUAL 0)
    message(FATAL_ERROR "Netplay overlay failed: ${details}${errors}")
  endif()
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${patcher}")
  get_target_property(sources libdevilutionx SOURCES)
  foreach(name tcp_client tcp_server protocol_zt zerotier_native zerotier_lwip)
    if(name STREQUAL "tcp_client" OR name STREQUAL "tcp_server" OR
       (name STREQUAL "protocol_zt" AND NOT DISABLE_ZERO_TIER) OR
       (name STREQUAL "zerotier_native" AND NOT DISABLE_ZERO_TIER) OR
       (name STREQUAL "zerotier_lwip" AND NOT DISABLE_ZERO_TIER))
      list(REMOVE_ITEM sources "dvlnet/${name}.cpp" "Source/dvlnet/${name}.cpp"
      "${PROJECT_SOURCE_DIR}/Source/dvlnet/${name}.cpp")
      list(APPEND sources "${output}/dvlnet/${name}.cpp")
    endif()
  endforeach()
  set_property(TARGET libdevilutionx PROPERTY SOURCES "${sources}")
  target_include_directories(libdevilutionx BEFORE PUBLIC "${output}")
endfunction()
cmake_language(DEFER CALL diablo_netplay_fixes)
