# Cross-compile ArtGraf for 64-bit Windows from Linux with MinGW-w64:
#   cmake -S . -B build-win -DCMAKE_TOOLCHAIN_FILE=cmake/mingw-w64-x86_64.cmake
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)
set(_prefix x86_64-w64-mingw32)
# The -posix variants support std::thread (used for multi-threaded compositing).
find_program(CMAKE_C_COMPILER NAMES ${_prefix}-gcc-posix ${_prefix}-gcc REQUIRED)
find_program(CMAKE_CXX_COMPILER NAMES ${_prefix}-g++-posix ${_prefix}-g++ REQUIRED)
find_program(CMAKE_RC_COMPILER NAMES ${_prefix}-windres REQUIRED)
set(CMAKE_FIND_ROOT_PATH /usr/${_prefix})
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
