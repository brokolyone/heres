#pragma once
#include <cstdint>
#include <random>
#include <string>
#include <vector>

#include "image.h"
#include "raster.h"

namespace ag {

// Grayscale brush tip: 0..255 coverage, square, centered.
struct BrushTip {
    int size = 0;
    std::vector<uint8_t> a;
    uint8_t at(int x, int y) const { return a[size_t(y) * size + x]; }
    bool valid() const { return size > 0; }
};

enum class TipShape {
    Round,      // procedural circle; uses hardness
    Square,
    Chalk,      // round with grainy holes
    Charcoal,   // rough irregular blob
    Spray,      // many fine specks
    Star,
    Leaf,
    Grass,
    Bristle,    // dry brush: parallel bristle dots
    Heart,
    Cloud,      // soft lumpy blob
    Splatter,
    Custom,     // user-defined from an image
};

struct BrushPreset {
    std::string name;
    TipShape shape = TipShape::Round;
    float size = 20.f;       // px
    float hardness = 0.8f;   // 0..1 (Round only)
    float spacing = 0.12f;   // fraction of size
    float angle = 0.f;       // degrees
    float roundness = 1.f;   // 0.05..1 (squash along the tip's Y axis)
    float scatter = 0.f;     // fraction of size, random offset perpendicular to the stroke
    int count = 1;           // dabs per step
    float sizeJitter = 0.f;  // 0..1
    float angleJitter = 0.f; // 0..1 (of 360°)
    float flowJitter = 0.f;  // 0..1
    float flow = 1.f;        // per-dab strength
    bool buildup = false;    // airbrush: dabs accumulate instead of max-combining
    bool followStroke = false;  // rotate the tip along the stroke direction
    bool aliased = false;       // hard pixel edges (pencil, pixel art)
    int customId = -1;       // index into custom tips when shape == Custom
};

// Built-in presets shown in the Brushes panel.
const std::vector<BrushPreset>& builtinBrushes();

// Builds (and caches) the base tip for a shape at a reference resolution.
const BrushTip& tipFor(TipShape shape, float hardness);
BrushTip tipFromImage(const Image& img);  // dark = paint, transparent = none

// Stamps one dab into `cov`: tip scaled to `diameter`, rotated by `angleDeg`, squashed by
// `roundness`, multiplied by `alpha` (0..1). buildup adds with saturation instead of max.
void stampTip(Coverage& cov, const BrushTip& tip, float cx, float cy, float diameter, float angleDeg,
              float roundness, float alpha, bool buildup, bool antialias = true);

// Applies a preset's dynamics for one stroke position and stamps the resulting dabs.
class BrushStamper {
public:
    BrushStamper() : rng(12345) {}
    void reset(uint32_t seed) { rng.seed(seed); lastDir = 0; }
    // dirDeg: stroke direction for followStroke/scatter
    Rect dab(Coverage& cov, const BrushPreset& p, const BrushTip& tip, float x, float y, float dirDeg, float opacityCap = 1.f);

private:
    std::mt19937 rng;
    float lastDir;
    float uni() { return std::uniform_real_distribution<float>(0.f, 1.f)(rng); }
};

}  // namespace ag
