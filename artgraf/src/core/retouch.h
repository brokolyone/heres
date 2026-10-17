#pragma once
#include <vector>

#include "image.h"
#include "raster.h"

namespace ag {

enum class RetouchMode { Blur, Sharpen, Smudge, Dodge, Burn, Sponge };

struct RetouchParams {
    RetouchMode mode = RetouchMode::Blur;
    float radius = 20.f, hardness = 0.5f, strength = 0.5f;
    int range = 1;          // dodge/burn: 0 shadows, 1 midtones, 2 highlights
    bool saturate = false;  // sponge: true = add saturation
};

// Modifies pixels under one brush dab. `mask` is the selection (may be empty).
// Returns the rect that changed.
class Retoucher {
public:
    void begin(const Image& img, float x, float y, const RetouchParams& p);
    Rect dab(Image& img, float x, float y, const RetouchParams& p, const std::vector<uint8_t>& mask);

private:
    Image smudgeBuf;  // carried paint for the smudge tool
    int bufR = 0;
};

// Healing: fills pixels where `region` > 0 with texture taken from a nearby area, blended so that
// colors match along the region's border. Returns the changed rect.
Rect healRegion(Image& img, const Coverage& region, const std::vector<uint8_t>& selMask);

}  // namespace ag
