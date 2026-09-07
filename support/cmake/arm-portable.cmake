# Candidate GCC 15.2 / glibc 2.27 cross-build. Archive identity is recorded in
# .mister/evidence/arm-portable-toolchain.json. Hardware admission is separate.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR armv7)
set(DIABLO_ARM_TOOLCHAIN_ROOT "/home/meath/.cache/diablo-toolchain-1.3.1/x-tools/armv7-neon-linux-gnueabihf"
    CACHE PATH "Verified portable ARM toolchain directory")
list(APPEND CMAKE_TRY_COMPILE_PLATFORM_VARIABLES DIABLO_ARM_TOOLCHAIN_ROOT)
set(_prefix "${DIABLO_ARM_TOOLCHAIN_ROOT}/bin/armv7-neon-linux-gnueabihf-")
set(CMAKE_C_COMPILER "${_prefix}gcc")
set(CMAKE_CXX_COMPILER "${_prefix}g++")
set(CMAKE_AR "${_prefix}ar")
set(CMAKE_RANLIB "${_prefix}ranlib")
execute_process(COMMAND "${CMAKE_C_COMPILER}" -print-sysroot
    OUTPUT_VARIABLE CMAKE_SYSROOT OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE _sysroot_result)
if(NOT _sysroot_result EQUAL 0 OR NOT IS_DIRECTORY "${CMAKE_SYSROOT}/usr/include")
    message(FATAL_ERROR "Verified portable ARM compiler/sysroot unavailable")
endif()
set(CMAKE_FIND_ROOT_PATH "${CMAKE_SYSROOT}")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
set(ENV{PKG_CONFIG_PATH} "")
set(ENV{PKG_CONFIG_LIBDIR} "${CMAKE_SYSROOT}/usr/lib/pkgconfig:${CMAKE_SYSROOT}/usr/share/pkgconfig")
set(ENV{PKG_CONFIG_SYSROOT_DIR} "${CMAKE_SYSROOT}")
set(CMAKE_C_FLAGS_INIT "-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard")
set(CMAKE_CXX_FLAGS_INIT "-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard")
