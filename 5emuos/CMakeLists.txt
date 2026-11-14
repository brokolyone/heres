cmake_minimum_required(VERSION 3.20)
project(5emuos LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Guest code uses the System V x86-64 ABI. On Windows, HLE functions must be
# compiled with __attribute__((sysv_abi)), which only Clang supports (MSVC cannot).
if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    message(FATAL_ERROR "5emuos must be built with Clang (on Windows: clang-cl or clang++ from LLVM / Visual Studio's Clang component).")
endif()

if(NOT CMAKE_SYSTEM_PROCESSOR MATCHES "AMD64|x86_64|amd64")
    message(FATAL_ERROR "5emuos runs guest code natively and needs an x86-64 host.")
endif()

add_executable(5emuos
    src/main.cpp
    src/common/log.cpp
    src/common/sha1.cpp
    src/core/nid.cpp
    src/core/memory.cpp
    src/core/linker.cpp
    src/loader/elf.cpp
    src/hle/symbols.cpp
    src/hle/libc.cpp
    src/hle/libkernel.cpp
)
target_include_directories(5emuos PRIVATE src)

if(WIN32)
    target_compile_definitions(5emuos PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)
endif()

# ---- Tests (Linux host: needs a compiler that emits ELF) -------------------
option(EMUOS_TESTS "Build tests" ON)
if(EMUOS_TESTS AND CMAKE_SYSTEM_NAME STREQUAL "Linux")
    enable_testing()

    add_executable(nid_test tests/nid_test.cpp src/core/nid.cpp src/common/sha1.cpp)
    target_include_directories(nid_test PRIVATE src)
    add_test(NAME nid COMMAND nid_test)

    # A tiny freestanding "guest" ELF that imports puts/printf/sceKernelUsleep
    # by NID, the same way real PS4/PS5 binaries name their imports.
    set(GUEST_ELF ${CMAKE_BINARY_DIR}/hello_guest.elf)
    add_custom_command(
        OUTPUT ${GUEST_ELF}
        COMMAND ${CMAKE_C_COMPILER} -x c -O1 -fPIC -fno-stack-protector -ffreestanding
                -nostdlib -shared -Wl,-e,_start -Wl,-z,now
                -o ${GUEST_ELF} ${CMAKE_SOURCE_DIR}/tests/hello_guest.c
        DEPENDS tests/hello_guest.c
        COMMENT "Building test guest ELF")
    add_custom_target(hello_guest ALL DEPENDS ${GUEST_ELF})

    add_test(NAME run_hello_guest COMMAND 5emuos ${GUEST_ELF})
    set_tests_properties(run_hello_guest PROPERTIES
        PASS_REGULAR_EXPRESSION "Hello from the guest! 42 0x2a ps5")
endif()
