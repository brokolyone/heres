#include "text.h"

#define STB_TRUETYPE_IMPLEMENTATION
#include <stb_truetype.h>

#include "io.h"

namespace ag {

struct Font::Impl {
    std::vector<uint8_t> data;
    stbtt_fontinfo info{};
};

Font::Font() = default;
Font::~Font() = default;
Font::Font(Font&&) noexcept = default;
Font& Font::operator=(Font&&) noexcept = default;

bool Font::load(const std::string& path) {
    auto p = std::make_unique<Impl>();
    if (!readFile(path, p->data) || p->data.empty()) return false;
    int offset = stbtt_GetFontOffsetForIndex(p->data.data(), 0);
    if (offset < 0 || !stbtt_InitFont(&p->info, p->data.data(), offset)) return false;
    impl = std::move(p);
    return true;
}

bool Font::ok() const { return impl != nullptr; }

std::vector<uint32_t> decodeUtf8(const std::string& s) {
    std::vector<uint32_t> out;
    for (size_t i = 0; i < s.size();) {
        uint8_t c = uint8_t(s[i]);
        uint32_t cp;
        int extra;
        if (c < 0x80) { cp = c; extra = 0; }
        else if ((c >> 5) == 6) { cp = c & 0x1f; extra = 1; }
        else if ((c >> 4) == 14) { cp = c & 0x0f; extra = 2; }
        else if ((c >> 3) == 30) { cp = c & 0x07; extra = 3; }
        else { i++; continue; }
        if (i + extra >= s.size() && extra > 0) break;  // truncated sequence
        for (int k = 1; k <= extra; k++) cp = (cp << 6) | (uint8_t(s[i + k]) & 0x3f);
        out.push_back(cp);
        i += extra + 1;
    }
    return out;
}

Rect Font::draw(Coverage* cov, const std::string& text, float x, float y, float size, float lineHeight) const {
    if (!impl || size <= 0) return {};
    const stbtt_fontinfo* f = &impl->info;
    float scale = stbtt_ScaleForMappingEmToPixels(f, size);
    int ascent, descent, gap;
    stbtt_GetFontVMetrics(f, &ascent, &descent, &gap);
    float lineStep = size * lineHeight;
    float baseline = y + ascent * scale;
    float penX = x;
    Rect area{};
    std::vector<uint8_t> glyph;
    uint32_t prev = 0;
    for (uint32_t cp : decodeUtf8(text)) {
        if (cp == '\n') {
            penX = x;
            baseline += lineStep;
            prev = 0;
            continue;
        }
        if (cp == '\r') continue;
        if (prev) penX += stbtt_GetCodepointKernAdvance(f, int(prev), int(cp)) * scale;
        int adv, lsb;
        stbtt_GetCodepointHMetrics(f, int(cp), &adv, &lsb);
        float fx = penX - std::floor(penX), fy = baseline - std::floor(baseline);
        int x0, y0, x1, y1;
        stbtt_GetCodepointBitmapBoxSubpixel(f, int(cp), scale, scale, fx, fy, &x0, &y0, &x1, &y1);
        int gw = x1 - x0, gh = y1 - y0;
        int ox = int(std::floor(penX)) + x0, oy = int(std::floor(baseline)) + y0;
        if (gw > 0 && gh > 0) {
            area = area.unite(Rect::of(ox, oy, gw, gh));
            if (cov) {
                glyph.assign(size_t(gw) * gh, 0);
                stbtt_MakeCodepointBitmapSubpixel(f, glyph.data(), gw, gh, gw, scale, scale, fx, fy, int(cp));
                Rect d = Rect::of(ox, oy, gw, gh).intersect({0, 0, cov->w, cov->h});
                if (!d.empty()) {
                    cov->touched = cov->touched.unite(d);
                    for (int yy = d.y0; yy < d.y1; yy++)
                        for (int xx = d.x0; xx < d.x1; xx++) {
                            uint8_t g = glyph[size_t(yy - oy) * gw + (xx - ox)];
                            if (g) cov->put(xx, yy, g / 255.f);
                        }
                }
            }
        }
        penX += adv * scale;
        prev = cp;
    }
    // Make an empty line or a trailing caret still have a size the UI can show.
    if (area.empty()) area = Rect::of(int(x), int(y), int(size * 0.5f), int(lineStep));
    return area;
}

}  // namespace ag
