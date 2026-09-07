# Cross-build preparation using the installed Debian/Ubuntu ARM compiler.
# This default sysroot is NOT admitted for MiSTer deployment without board ABI
# verification. Keep host package discovery out of the target dependency graph.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR armv7)
set(CMAKE_C_COMPILER arm-linux-gnueabihf-gcc)
set(CMAKE_CXX_COMPILER arm-linux-gnueabihf-g++)
set(CMAKE_AR arm-linux-gnueabihf-ar)
set(CMAKE_RANLIB arm-linux-gnueabihf-ranlib)
# Debian's cross GCC also searches host /usr/include unless compilation gets
# an explicit sysroot. Keep its default link search: the cross libc linker
# scripts contain Debian's absolute /usr/arm-linux-gnueabihf paths.
set(CMAKE_SYSROOT_COMPILE /usr/arm-linux-gnueabihf)
set(CMAKE_FIND_ROOT_PATH /usr/arm-linux-gnueabihf)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
set(ENV{PKG_CONFIG_PATH} "")
set(ENV{PKG_CONFIG_LIBDIR} "/usr/arm-linux-gnueabihf/lib/pkgconfig:/usr/lib/arm-linux-gnueabihf/pkgconfig")
set(CMAKE_C_FLAGS_INIT "-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard")
set(CMAKE_CXX_FLAGS_INIT "-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard")
