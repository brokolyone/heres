#pragma once
#include "image.h"

namespace ag {

enum class BlendMode {
    Normal, Darken, Multiply, ColorBurn, LinearBurn,
    Lighten, Screen, ColorDodge, Add,
    Overlay, SoftLight, HardLight,
    Difference, Exclusion, Subtract,
    Count
};

const char* blendName(BlendMode m);
const char* blendId(BlendMode m);           // stable id for project files
BlendMode blendFromId(const char* id);

// Composite src (straight alpha) onto dst with the given mode; opacity multiplies src alpha.
RGBA blendPixel(RGBA dst, RGBA src, BlendMode mode, float opacity);

}  // namespace ag
