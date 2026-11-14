#include "core/nid.h"

#include <vector>
#include "common/sha1.h"

namespace Core::Nid {
namespace {
constexpr u8 kSalt[16] = {0x51, 0x8D, 0x64, 0xA6, 0x35, 0xDE, 0xD8, 0xC1,
                          0xE6, 0xB0, 0x39, 0xB1, 0xC3, 0xE5, 0x52, 0x30};
// Standard base64, but '/' is replaced by '-' so the result is filename/symbol safe.
constexpr char kAlphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-";
} // namespace

std::string FromName(std::string_view name) {
    std::vector<u8> buf(name.begin(), name.end());
    buf.insert(buf.end(), std::begin(kSalt), std::end(kSalt));
    const auto digest = Common::Sha1(buf);

    // First 8 digest bytes read as a little-endian u64, then base64'd big-endian.
    u64 value = 0;
    for (int i = 7; i >= 0; --i) {
        value = (value << 8) | digest[i];
    }
    // 64 bits -> 11 sextets; the last one only holds 4 bits (shifted left by 2).
    std::string out;
    out.reserve(11);
    for (int i = 0; i < 10; ++i) {
        out.push_back(kAlphabet[(value >> (58 - i * 6)) & 0x3F]);
    }
    out.push_back(kAlphabet[(value & 0xF) << 2]);
    return out;
}

std::optional<u16> DecodeId(std::string_view s) {
    if (s.empty() || s.size() > 3) {
        return std::nullopt;
    }
    u32 value = 0;
    for (char c : s) {
        const char* pos = nullptr;
        for (const char* p = kAlphabet; *p; ++p) {
            if (*p == c) {
                pos = p;
                break;
            }
        }
        if (!pos) {
            return std::nullopt;
        }
        value = (value << 6) | static_cast<u32>(pos - kAlphabet);
    }
    return static_cast<u16>(value);
}

SymbolName Parse(std::string_view encoded) {
    SymbolName out;
    const auto first = encoded.find('#');
    if (first == std::string_view::npos) {
        out.nid = std::string(encoded);
        return out;
    }
    out.nid = std::string(encoded.substr(0, first));
    const auto rest = encoded.substr(first + 1);
    const auto second = rest.find('#');
    if (second == std::string_view::npos) {
        return out;
    }
    const auto lib = DecodeId(rest.substr(0, second));
    const auto mod = DecodeId(rest.substr(second + 1));
    if (lib && mod) {
        out.library_id = *lib;
        out.module_id = *mod;
        out.has_ids = true;
    }
    return out;
}

} // namespace Core::Nid
