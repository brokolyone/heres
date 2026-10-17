#pragma once
#include <string>
#include <vector>

#include "image.h"

namespace ag {

struct GradientStop {
    float pos;  // 0..1
    RGBA color;
};

struct Gradient {
    std::string name;
    std::vector<GradientStop> stops;  // sorted by pos, at least one

    RGBA sample(float t) const;
    void sort();
    Gradient reversed() const;
};

enum class GradientType { Linear, Radial, Angle, Reflected, Diamond, Count };
const char* gradientTypeName(GradientType t);

// Position along the gradient (0..1, clamped) of pixel center (px, py) for a drag from a to b.
float gradientT(GradientType type, float ax, float ay, float bx, float by, float px, float py);

// Presets; the first two follow the current primary/secondary colors.
std::vector<Gradient> gradientPresets(RGBA primary, RGBA secondary);

}  // namespace ag
