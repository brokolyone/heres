cmake_minimum_required(VERSION 3.20)
project(ArtGraf VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release)
endif()
# Static MSVC runtime for every target, so the .exe needs no VC++ redistributable.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

option(ARTGRAF_BUILD_APP "Build the ArtGraf GUI application" ON)
option(ARTGRAF_BUILD_TESTS "Build the core library tests" ON)
if(WIN32)
  set(_nfd_default ON)
else()
  set(_nfd_default OFF)  # needs GTK3 or xdg-portal on Linux; the built-in file browser is used instead
endif()
option(ARTGRAF_NATIVE_DIALOGS "Use nativefiledialog-extended for open/save dialogs" ${_nfd_default})

include(FetchContent)
set(FETCHCONTENT_QUIET ON)

# ---------------------------------------------------------------- dependencies

# Header-only stb: stb_image, stb_image_write, stb_image_resize2, stb_truetype
FetchContent_Declare(stb
  GIT_REPOSITORY https://github.com/nothings/stb.git
  GIT_TAG 2c980bb59875b0d32144a71867fbdebb2f77cd20
  SOURCE_SUBDIR _none)

# JSON for the project file metadata
FetchContent_Declare(json
  URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
  URL_HASH SHA256=d6c65aca6b1ed68e7a182f4757257b107ae403032760ed6ef121c9d55e81757d)

# Zip container for .agf projects
FetchContent_Declare(miniz
  URL https://github.com/richgel999/miniz/releases/download/3.0.2/miniz-3.0.2.zip
  URL_HASH SHA256=ada38db0b703a56d3dd6d57bf84a9c5d664921d870d8fea4db153979fb5332c5
  SOURCE_SUBDIR _none)

set(JSON_BuildTests OFF CACHE INTERNAL "")
FetchContent_MakeAvailable(stb json miniz)

add_library(miniz STATIC ${miniz_SOURCE_DIR}/miniz.c)
target_include_directories(miniz PUBLIC ${miniz_SOURCE_DIR})

# ---------------------------------------------------------------- core library

add_library(artgraf_core STATIC
  src/core/image.cpp
  src/core/blend.cpp
  src/core/document.cpp
  src/core/filters.cpp
  src/core/raster.cpp
  src/core/text.cpp
  src/core/io.cpp)
target_include_directories(artgraf_core PUBLIC src/core ${stb_SOURCE_DIR})
target_link_libraries(artgraf_core PUBLIC nlohmann_json::nlohmann_json miniz)
if(MSVC)
  target_compile_options(artgraf_core PRIVATE /utf-8 /W3)
else()
  target_compile_options(artgraf_core PRIVATE -Wall -Wextra -Wno-missing-field-initializers)
endif()

if(ARTGRAF_BUILD_TESTS AND NOT CMAKE_CROSSCOMPILING)
  enable_testing()
  add_executable(artgraf_tests tests/core_tests.cpp)
  target_link_libraries(artgraf_tests PRIVATE artgraf_core)
  add_test(NAME core COMMAND artgraf_tests)
endif()

if(NOT ARTGRAF_BUILD_APP)
  return()
endif()

# ---------------------------------------------------------------- application

FetchContent_Declare(SDL2
  URL https://github.com/libsdl-org/SDL/releases/download/release-2.30.9/SDL2-2.30.9.tar.gz
  URL_HASH SHA256=24b574f71c87a763f50704bbb630cbe38298d544a1f890f099a4696b1d6beba4)
set(SDL_SHARED OFF CACHE BOOL "" FORCE)
set(SDL_STATIC ON CACHE BOOL "" FORCE)
set(SDL_TEST OFF CACHE BOOL "" FORCE)
set(SDL2_DISABLE_INSTALL ON CACHE BOOL "" FORCE)

# Dear ImGui, docking branch (dockable panels)
FetchContent_Declare(imgui
  GIT_REPOSITORY https://github.com/ocornut/imgui.git
  GIT_TAG v1.91.5-docking
  SOURCE_SUBDIR _none)

FetchContent_MakeAvailable(SDL2 imgui)

add_library(imgui STATIC
  ${imgui_SOURCE_DIR}/imgui.cpp
  ${imgui_SOURCE_DIR}/imgui_draw.cpp
  ${imgui_SOURCE_DIR}/imgui_tables.cpp
  ${imgui_SOURCE_DIR}/imgui_widgets.cpp
  ${imgui_SOURCE_DIR}/backends/imgui_impl_sdl2.cpp
  ${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp
  ${imgui_SOURCE_DIR}/misc/cpp/imgui_stdlib.cpp)
target_include_directories(imgui PUBLIC ${imgui_SOURCE_DIR} ${imgui_SOURCE_DIR}/backends ${imgui_SOURCE_DIR}/misc/cpp)
target_link_libraries(imgui PUBLIC SDL2::SDL2-static)

find_package(OpenGL REQUIRED)

set(APP_SOURCES
  src/app/main.cpp
  src/app/editor.cpp
  src/app/editor_ui.cpp
  src/app/editor_tools.cpp
  src/app/file_dialog.cpp
  src/app/clipboard.cpp
  src/app/icons.cpp)
if(WIN32)
  list(APPEND APP_SOURCES res/artgraf.rc)
endif()

add_executable(artgraf WIN32 ${APP_SOURCES})
target_include_directories(artgraf PRIVATE src/app)
target_link_libraries(artgraf PRIVATE artgraf_core imgui SDL2::SDL2main OpenGL::GL)

if(ARTGRAF_NATIVE_DIALOGS)
  FetchContent_Declare(nfd
    GIT_REPOSITORY https://github.com/btzy/nativefiledialog-extended.git
    GIT_TAG v1.2.1)
  set(NFD_INSTALL OFF CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(nfd)
  target_link_libraries(artgraf PRIVATE nfd)
  target_compile_definitions(artgraf PRIVATE ARTGRAF_NFD=1)
endif()

if(MSVC)
  target_compile_options(artgraf PRIVATE /utf-8)
elseif(MINGW)
  # One self-contained .exe: no libstdc++/libgcc/winpthread DLLs next to it.
  target_link_options(artgraf PRIVATE -static -static-libgcc -static-libstdc++ $<$<CONFIG:Release>:-s>)
endif()
set_target_properties(artgraf PROPERTIES OUTPUT_NAME "ArtGraf")
