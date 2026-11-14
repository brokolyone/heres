#pragma once
#include "common/types.h"

namespace Core::Memory {

// Allocates RWX host memory for guest code/data. If `fixed_address` is non-zero
// the allocation must land exactly there (needed for non-relocatable executables).
// Returns nullptr on failure.
void* Allocate(u64 size, u64 fixed_address = 0);
void Free(void* ptr, u64 size);

constexpr u64 kPageSize = 0x4000; // PS4/PS5 use 16 KiB pages.

constexpr u64 AlignUp(u64 value, u64 align) {
    return (value + align - 1) & ~(align - 1);
}
constexpr u64 AlignDown(u64 value, u64 align) {
    return value & ~(align - 1);
}

} // namespace Core::Memory
