// HLE implementation of the guest's C library. Real games ship their own libc
// as a system module (libSceLibcInternal); we replace it function by function.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include "common/log.h"
#include "hle/symbols.h"

namespace HLE::Libc {
namespace {

// Variadic functions can't simply be forwarded across ABIs (on Windows the host
// va_list differs from System V). Instead we receive the integer argument
// registers explicitly and run our own formatter over them.
// TODO: floating point args (passed in xmm0-7) and stack arguments.
std::string FormatGuest(const char* fmt, const u64* args, int arg_count) {
    std::string out;
    int next = 0;
    auto take = [&]() -> u64 { return next < arg_count ? args[next++] : 0; };

    for (const char* p = fmt; *p; ++p) {
        if (*p != '%') {
            out.push_back(*p);
            continue;
        }
        if (p[1] == '%') {
            out.push_back('%');
            ++p;
            continue;
        }
        // Collect flags/width/precision, drop length modifiers, find conversion.
        std::string spec = "%";
        ++p;
        while (*p && std::strchr("-+ #0123456789.", *p)) spec.push_back(*p++);
        while (*p && std::strchr("hlLqjzt", *p)) ++p;
        if (!*p) break;

        char buf[512];
        const char conv = *p;
        switch (conv) {
        case 'd':
        case 'i':
            std::snprintf(buf, sizeof(buf), (spec + "lld").c_str(), static_cast<long long>(take()));
            break;
        case 'u':
        case 'x':
        case 'X':
        case 'o':
            std::snprintf(buf, sizeof(buf), (spec + "ll" + conv).c_str(),
                          static_cast<unsigned long long>(take()));
            break;
        case 'c':
            std::snprintf(buf, sizeof(buf), (spec + "c").c_str(), static_cast<int>(take()));
            break;
        case 'p':
            std::snprintf(buf, sizeof(buf), "0x%llx", static_cast<unsigned long long>(take()));
            break;
        case 's': {
            const char* s = reinterpret_cast<const char*>(take());
            std::snprintf(buf, sizeof(buf), (spec + "s").c_str(), s ? s : "(null)");
            break;
        }
        default:
            std::snprintf(buf, sizeof(buf), "<%%%c unsupported>", conv);
            take();
            break;
        }
        out += buf;
    }
    return out;
}

int PS5_SYSV_ABI Printf(const char* fmt, u64 a1, u64 a2, u64 a3, u64 a4, u64 a5) {
    const u64 args[] = {a1, a2, a3, a4, a5};
    const auto text = FormatGuest(fmt, args, 5);
    std::fputs(text.c_str(), stdout);
    std::fflush(stdout);
    return static_cast<int>(text.size());
}

int PS5_SYSV_ABI Puts(const char* s) {
    std::puts(s);
    std::fflush(stdout);
    return 0;
}

void PS5_SYSV_ABI Exit(int code) {
    LOG_INFO("HLE.libc", "Guest called exit({})", code);
    std::fflush(stdout);
    std::exit(code);
}

u64 PS5_SYSV_ABI Strlen(const char* s) {
    return std::strlen(s);
}

void* PS5_SYSV_ABI Memcpy(void* dst, const void* src, u64 n) {
    return std::memcpy(dst, src, n);
}

void* PS5_SYSV_ABI Memset(void* dst, int value, u64 n) {
    return std::memset(dst, value, n);
}

int PS5_SYSV_ABI Strcmp(const char* a, const char* b) {
    return std::strcmp(a, b);
}

} // namespace

void RegisterFunctions() {
    Register("libc", "printf", reinterpret_cast<void*>(&Printf));
    Register("libc", "puts", reinterpret_cast<void*>(&Puts));
    Register("libc", "exit", reinterpret_cast<void*>(&Exit));
    Register("libc", "strlen", reinterpret_cast<void*>(&Strlen));
    Register("libc", "memcpy", reinterpret_cast<void*>(&Memcpy));
    Register("libc", "memset", reinterpret_cast<void*>(&Memset));
    Register("libc", "strcmp", reinterpret_cast<void*>(&Strcmp));
}

} // namespace HLE::Libc
