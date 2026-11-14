#include "common/sha1.h"

#include <vector>

namespace Common {
namespace {
constexpr u32 Rol(u32 v, int n) {
    return (v << n) | (v >> (32 - n));
}
} // namespace

std::array<u8, 20> Sha1(std::span<const u8> data) {
    u32 h[5] = {0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0};

    std::vector<u8> msg(data.begin(), data.end());
    const u64 bit_len = static_cast<u64>(data.size()) * 8;
    msg.push_back(0x80);
    while (msg.size() % 64 != 56) {
        msg.push_back(0);
    }
    for (int i = 7; i >= 0; --i) {
        msg.push_back(static_cast<u8>(bit_len >> (i * 8)));
    }

    for (size_t chunk = 0; chunk < msg.size(); chunk += 64) {
        u32 w[80];
        for (int i = 0; i < 16; ++i) {
            const u8* p = &msg[chunk + i * 4];
            w[i] = (u32{p[0]} << 24) | (u32{p[1]} << 16) | (u32{p[2]} << 8) | u32{p[3]};
        }
        for (int i = 16; i < 80; ++i) {
            w[i] = Rol(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
        }
        u32 a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
        for (int i = 0; i < 80; ++i) {
            u32 f, k;
            if (i < 20) {
                f = (b & c) | (~b & d);
                k = 0x5A827999;
            } else if (i < 40) {
                f = b ^ c ^ d;
                k = 0x6ED9EBA1;
            } else if (i < 60) {
                f = (b & c) | (b & d) | (c & d);
                k = 0x8F1BBCDC;
            } else {
                f = b ^ c ^ d;
                k = 0xCA62C1D6;
            }
            const u32 t = Rol(a, 5) + f + e + k + w[i];
            e = d;
            d = c;
            c = Rol(b, 30);
            b = a;
            a = t;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
    }

    std::array<u8, 20> out{};
    for (int i = 0; i < 5; ++i) {
        out[i * 4 + 0] = static_cast<u8>(h[i] >> 24);
        out[i * 4 + 1] = static_cast<u8>(h[i] >> 16);
        out[i * 4 + 2] = static_cast<u8>(h[i] >> 8);
        out[i * 4 + 3] = static_cast<u8>(h[i]);
    }
    return out;
}

} // namespace Common
