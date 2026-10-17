#include "clipboard.h"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <cstring>
#include <string>

#include "io.h"

namespace ag {

namespace {

bool fromDib(const uint8_t* data, size_t size, Image& out) {
    if (size < sizeof(BITMAPINFOHEADER)) return false;
    BITMAPINFOHEADER bi;
    std::memcpy(&bi, data, sizeof bi);
    if (bi.biBitCount != 32 && bi.biBitCount != 24) return false;
    if (bi.biCompression != BI_RGB && bi.biCompression != BI_BITFIELDS) return false;
    int w = bi.biWidth, h = bi.biHeight < 0 ? -bi.biHeight : bi.biHeight;
    bool bottomUp = bi.biHeight > 0;
    if (w <= 0 || h <= 0) return false;
    size_t offset = bi.biSize + (bi.biCompression == BI_BITFIELDS && bi.biSize == 40 ? 12 : 0) + bi.biClrUsed * 4;
    int bpp = bi.biBitCount / 8;
    size_t stride = (size_t(w) * bpp + 3) & ~size_t(3);
    if (offset + stride * h > size) return false;
    out = Image(w, h);
    bool anyAlpha = false;
    for (int y = 0; y < h; y++) {
        const uint8_t* row = data + offset + stride * (bottomUp ? h - 1 - y : y);
        for (int x = 0; x < w; x++) {
            const uint8_t* p = row + x * bpp;
            uint8_t a = bpp == 4 ? p[3] : 255;
            anyAlpha |= a != 0;
            out.set(x, y, {p[2], p[1], p[0], a});
        }
    }
    if (!anyAlpha)  // most apps leave the alpha byte at zero
        for (size_t i = 3; i < out.px.size(); i += 4) out.px[i] = 255;
    return true;
}

bool putGlobal(UINT format, const void* data, size_t size) {
    HGLOBAL h = GlobalAlloc(GMEM_MOVEABLE, size);
    if (!h) return false;
    void* p = GlobalLock(h);
    std::memcpy(p, data, size);
    GlobalUnlock(h);
    if (!SetClipboardData(format, h)) {
        GlobalFree(h);
        return false;
    }
    return true;
}

}  // namespace

bool clipboardGetImage(Image& out) {
    if (!OpenClipboard(nullptr)) return false;
    bool ok = false;
    UINT png = RegisterClipboardFormatA("PNG");
    if (HANDLE h = IsClipboardFormatAvailable(png) ? GetClipboardData(png) : nullptr) {
        if (auto* p = static_cast<const uint8_t*>(GlobalLock(h))) {
            std::vector<uint8_t> bytes(p, p + GlobalSize(h));
            GlobalUnlock(h);
            std::string err;
            ok = decodeImage(bytes, out, err);
        }
    }
    if (!ok) {
        if (HANDLE h = IsClipboardFormatAvailable(CF_DIB) ? GetClipboardData(CF_DIB) : nullptr) {
            if (auto* p = static_cast<const uint8_t*>(GlobalLock(h))) {
                ok = fromDib(p, GlobalSize(h), out);
                GlobalUnlock(h);
            }
        }
    }
    CloseClipboard();
    return ok;
}

bool clipboardSetImage(const Image& img) {
    if (!img.valid() || !OpenClipboard(nullptr)) return false;
    EmptyClipboard();
    std::vector<uint8_t> png = encodePng(img);
    bool ok = putGlobal(RegisterClipboardFormatA("PNG"), png.data(), png.size());

    BITMAPINFOHEADER bi{};
    bi.biSize = sizeof bi;
    bi.biWidth = img.w;
    bi.biHeight = img.h;  // bottom-up
    bi.biPlanes = 1;
    bi.biBitCount = 32;
    bi.biCompression = BI_RGB;
    std::vector<uint8_t> dib(sizeof bi + size_t(img.w) * img.h * 4);
    std::memcpy(dib.data(), &bi, sizeof bi);
    uint8_t* dst = dib.data() + sizeof bi;
    for (int y = 0; y < img.h; y++)
        for (int x = 0; x < img.w; x++) {
            // Pre-composite on white: apps that ignore DIB alpha would show black otherwise.
            RGBA c = over({255, 255, 255, 255}, img.get(x, img.h - 1 - y));
            uint8_t* p = dst + (size_t(y) * img.w + x) * 4;
            p[0] = c.b; p[1] = c.g; p[2] = c.r; p[3] = 255;
        }
    ok = putGlobal(CF_DIB, dib.data(), dib.size()) || ok;
    CloseClipboard();
    return ok;
}

}  // namespace ag

#else

namespace ag {
bool clipboardGetImage(Image&) { return false; }
bool clipboardSetImage(const Image&) { return false; }
}  // namespace ag

#endif
