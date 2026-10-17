#pragma once
#include <memory>
#include <string>
#include <vector>

#include "raster.h"

namespace ag {

class Font {
public:
    Font();
    ~Font();
    Font(Font&&) noexcept;
    Font& operator=(Font&&) noexcept;

    bool load(const std::string& path);
    bool ok() const;

    // Render UTF-8 text (with '\n' line breaks) into `cov`, top-left corner at (x, y).
    // `size` is the em size in pixels. Returns the area the text occupies.
    Rect draw(Coverage* cov, const std::string& text, float x, float y, float size, float lineHeight = 1.2f) const;
    Rect measure(const std::string& text, float x, float y, float size, float lineHeight = 1.2f) const {
        return draw(nullptr, text, x, y, size, lineHeight);
    }

private:
    struct Impl;
    std::unique_ptr<Impl> impl;
};

std::vector<uint32_t> decodeUtf8(const std::string& s);

}  // namespace ag
