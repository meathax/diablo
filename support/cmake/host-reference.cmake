# Project-owned host integration; the pinned engine checkout stays unchanged.
if(WIN32 AND MINGW)
  function(diablo_host_patch_file relative expected before after output)
    set(original "${PROJECT_SOURCE_DIR}/Source/${relative}")
    file(SHA256 "${original}" observed)
    if(NOT observed STREQUAL expected)
      message(FATAL_ERROR "Unexpected engine input for host patch: ${relative}")
    endif()
    file(READ "${original}" content)
    string(REPLACE "${before}" "${after}" content "${content}")
    file(CONFIGURE OUTPUT "${output}" CONTENT "${content}" @ONLY NEWLINE_STYLE UNIX)
    file(SHA256 "${output}" patched)
    file(APPEND "${CMAKE_BINARY_DIR}/host-engine-fixes.txt" "${relative} ${observed} ${patched}\n")
  endfunction()

  find_library(DIABLO_HOST_INTL_LIBRARY NAMES intl REQUIRED)
  function(diablo_link_host_dependencies)
    set(overlay "${CMAKE_BINARY_DIR}/host-engine-overlay")
    file(WRITE "${CMAKE_BINARY_DIR}/host-engine-fixes.txt" "Original and generated SHA256; pinned checkout remains unchanged.\n")
    # Windows absolute drive and UNC paths must bypass archive/asset prefixes.
    diablo_host_patch_file(engine/assets.cpp
      aa1e0838afd94fa634a722146cee503f227c5bd4bbbdfc586e07e6086e54a5db
      [[if (relativePath[0] == '/')]]
      [[if (relativePath[0] == '/' || relativePath[0] == '\\'
        || (filename.size() >= 3
            && ((relativePath[0] >= 'A' && relativePath[0] <= 'Z')
                || (relativePath[0] >= 'a' && relativePath[0] <= 'z'))
            && relativePath[1] == ':'
            && (relativePath[2] == '/' || relativePath[2] == '\\')))]]
      "${overlay}/engine/assets.cpp")
    set_property(TARGET libdevilutionx_assets PROPERTY SOURCES "${overlay}/engine/assets.cpp")
    diablo_host_patch_file(utils/png.h
      cc755c3c8f58859a5e68c95ad6d2156ab50a21cb6a362e87d6b7afedb6223d5a
      [[auto *rwops = OpenAssetAsSdlRwOps(file);]]
      [[auto *rwops = OpenAssetAsSdlRwOps(file);
    if (rwops == nullptr)
        return nullptr;]]
      "${overlay}/utils/png.h")
    # Only these translation units include utils/png.h in this pinned revision.
    set_property(SOURCE "${PROJECT_SOURCE_DIR}/Source/controls/touch/renderers.cpp" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
      APPEND PROPERTY INCLUDE_DIRECTORIES "${overlay}")
    if(TARGET text_render_integration_test)
      target_include_directories(text_render_integration_test BEFORE PRIVATE "${overlay}")
      target_sources(text_render_integration_test PRIVATE "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../tests/host_png_test.cpp")
    endif()
    # language.h includes GNU libintl.h; its printf redirects need the library.
    target_link_libraries(libdevilutionx PUBLIC "${DIABLO_HOST_INTL_LIBRARY}")
    # SDL startup belongs to the game executable (already linked upstream),
    # not every library consumer. GoogleTest/benchmark supply console main().
    get_target_property(sdl_libraries DevilutionX::SDL INTERFACE_LINK_LIBRARIES)
    list(REMOVE_ITEM sdl_libraries SDL2::SDL2main)
    set_property(TARGET DevilutionX::SDL PROPERTY INTERFACE_LINK_LIBRARIES "${sdl_libraries}")
    if(TARGET test_main)
      add_executable(mister_controller_test "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../tests/mister_controller_test.cpp")
      set_target_properties(mister_controller_test PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}")
      target_link_libraries(mister_controller_test PRIVATE test_main)
      list(APPEND tests mister_controller_test)
      gtest_discover_tests(mister_controller_test)
      # MinGW/LTO DLL auto-export fails on C++ template symbols. Link the same
      # engine objects directly into tests, without changing test assertions.
      foreach(link_property LINK_LIBRARIES INTERFACE_LINK_LIBRARIES)
        get_target_property(test_links test_main ${link_property})
        list(TRANSFORM test_links REPLACE "^libdevilutionx_so$" "libdevilutionx")
        set_property(TARGET test_main PROPERTY ${link_property} "${test_links}")
      endforeach()
      get_target_property(engine_objects libdevilutionx LINKED_OBJECTS)
      foreach(engine_test IN LISTS tests)
        target_sources(${engine_test} PRIVATE ${engine_objects} $<TARGET_OBJECTS:libdevilutionx>)
      endforeach()
      set_property(TARGET libdevilutionx_so PROPERTY EXCLUDE_FROM_ALL TRUE)
      target_compile_definitions(test_main PRIVATE SDL_MAIN_HANDLED)
      foreach(host_test IN LISTS tests standalone_tests benchmarks)
        target_compile_definitions(${host_test} PRIVATE SDL_MAIN_HANDLED)
        target_link_libraries(${host_test} PRIVATE "${DIABLO_HOST_INTL_LIBRARY}")
      endforeach()
      # These standalone upstream tests include gmock matchers directly.
      target_link_libraries(crawl_test PRIVATE GTest::gmock)
      target_link_libraries(path_test PRIVATE GTest::gmock)
      target_link_libraries(ini_test PRIVATE GTest::gmock)
      add_custom_target(diablo_host_tests DEPENDS ${tests} ${standalone_tests} ${benchmarks})
      foreach(zlib_test example example64)
        if(TARGET ${zlib_test})
          add_dependencies(diablo_host_tests ${zlib_test})
        endif()
      endforeach()
    endif()
    include("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/host-capture.cmake")
    include("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/host-scenario.cmake")
    include("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/replay-loading.cmake")
    include("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/mister-controller.cmake")
  endfunction()
  cmake_language(DEFER CALL diablo_link_host_dependencies)
endif()
