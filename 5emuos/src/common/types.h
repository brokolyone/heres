#pragma once
#include <cstddef>
#include <cstdint>

using u8 = std::uint8_t;
using u16 = std::uint16_t;
using u32 = std::uint32_t;
using u64 = std::uint64_t;
using s8 = std::int8_t;
using s16 = std::int16_t;
using s32 = std::int32_t;
using s64 = std::int64_t;
using VAddr = std::uint64_t;

// Every function the guest calls into must use the System V ABI, because that
// is what PS4/PS5 code is compiled for. On Linux this is the native ABI; on
// Windows Clang emits the right prologue thanks to this attribute.
#define PS5_SYSV_ABI __attribute__((sysv_abi))
