#include "core/memory.h"

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif

namespace Core::Memory {

void* Allocate(u64 size, u64 fixed_address) {
#ifdef _WIN32
    void* ptr = VirtualAlloc(reinterpret_cast<void*>(fixed_address), size,
                             MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    if (fixed_address && ptr != reinterpret_cast<void*>(fixed_address)) {
        if (ptr) VirtualFree(ptr, 0, MEM_RELEASE);
        return nullptr;
    }
    return ptr;
#else
    int flags = MAP_PRIVATE | MAP_ANONYMOUS;
    if (fixed_address) {
        flags |= MAP_FIXED_NOREPLACE;
    }
    void* ptr = mmap(reinterpret_cast<void*>(fixed_address), size,
                     PROT_READ | PROT_WRITE | PROT_EXEC, flags, -1, 0);
    return ptr == MAP_FAILED ? nullptr : ptr;
#endif
}

void Free(void* ptr, u64 size) {
    if (!ptr) return;
#ifdef _WIN32
    (void)size;
    VirtualFree(ptr, 0, MEM_RELEASE);
#else
    munmap(ptr, size);
#endif
}

} // namespace Core::Memory
