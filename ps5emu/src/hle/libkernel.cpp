// HLE implementation of libkernel: the guest's interface to the PS5 OS kernel
// (threads, memory, time, files...). This file will grow a lot.
#include <chrono>
#include <thread>
#include "common/log.h"
#include "hle/symbols.h"

namespace HLE::LibKernel {
namespace {

constexpr s32 ORBIS_OK = 0;

s32 PS5_SYSV_ABI sceKernelUsleep(u32 microseconds) {
    std::this_thread::sleep_for(std::chrono::microseconds(microseconds));
    return ORBIS_OK;
}

u64 PS5_SYSV_ABI sceKernelGetProcessTime() {
    static const auto start = std::chrono::steady_clock::now();
    const auto elapsed = std::chrono::steady_clock::now() - start;
    return static_cast<u64>(std::chrono::duration_cast<std::chrono::microseconds>(elapsed).count());
}

s32 PS5_SYSV_ABI getpid() {
    return 1;
}

} // namespace

void RegisterFunctions() {
    HLE_REGISTER("libkernel", sceKernelUsleep);
    HLE_REGISTER("libkernel", sceKernelGetProcessTime);
    HLE_REGISTER("libkernel", getpid);
}

} // namespace HLE::LibKernel
