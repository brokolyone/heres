#pragma once
#include <cstdint>
#include <vector>

#include "image.h"

namespace ag {

// Blur a single float plane in place (three box passes ≈ gaussian with sigma ≈ radius).
void gaussianPlane(float* data, int w, int h, float radius);

// Adjustments
void brightnessContrast(Image& img, float brightness, float contrast);  // both -100..100
void hueSaturation(Image& img, float hue, float saturation, float lightness);  // -180..180, -100..100, -100..100
void levels(Image& img, int inBlack, int inWhite, float gamma, int outBlack, int outWhite);
void colorBalance(Image& img, float cyanRed, float magentaGreen, float yellowBlue);  // -100..100
void autoContrast(Image& img);
void invert(Image& img);
void desaturate(Image& img);
void sepia(Image& img);
void posterize(Image& img, int levels);
void threshold(Image& img, int level);

// Filters
void gaussianBlur(Image& img, float radius);
void motionBlur(Image& img, float angleDeg, int distance);
void unsharpMask(Image& img, float radius, float amount, int thresholdLevel);
void addNoise(Image& img, float amount, bool monochrome, uint32_t seed);
void pixelate(Image& img, int cell);
void emboss(Image& img);
void findEdges(Image& img);
void vignette(Image& img, float amount);
void oilPaint(Image& img, int radius, int levels);

// Blend `filtered` into `img` weighted by the selection mask (empty mask = take filtered as is).
void applyMasked(Image& img, const Image& filtered, const std::vector<uint8_t>& mask);

}  // namespace ag
