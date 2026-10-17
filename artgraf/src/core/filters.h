#pragma once
#include <cstdint>
#include <vector>

#include "gradient.h"
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

// More adjustments
void curveLut(const std::vector<std::pair<float, float>>& pts, uint8_t out[256]);  // points in 0..255, monotone cubic
void applyLuts(Image& img, const uint8_t* r, const uint8_t* g, const uint8_t* b);
void vibrance(Image& img, float vibrance, float saturation);  // -100..100
void exposure(Image& img, float ev, float offset, float gamma);
void photoFilter(Image& img, RGBA color, float density, bool preserveLuminosity);
void blackWhite(Image& img, float reds, float yellows, float greens, float cyans, float blues, float magentas);
void gradientMap(Image& img, const Gradient& g);
void channelMixer(Image& img, float rr, float rg, float rb, float gr, float gg, float gb, float br, float bg, float bb);

// More filters
void zoomBlur(Image& img, float amount);           // 0..100
void spinBlur(Image& img, float angleDeg);
void tiltShift(Image& img, float focusCenter, float focusSize, float blur);  // center/size as 0..1 of height
void twirl(Image& img, float angleDeg);
void spherize(Image& img, float amount);           // -100..100
void wave(Image& img, float amplitude, float wavelength);
void ripple(Image& img, float amount, float size);
void polarCoordinates(Image& img, bool rectToPolar);
void halftone(Image& img, int cell);
void glitch(Image& img, float shift, int slices, uint32_t seed);
void chromaticAberration(Image& img, float px);
void renderClouds(Image& img, RGBA fg, RGBA bg, float scale, uint32_t seed);
void lensFlare(Image& img, float cx, float cy, float brightness);
void median(Image& img, int radius);
void crystallize(Image& img, int cell, uint32_t seed);
void sketch(Image& img, float strength);
void solarize(Image& img);

// Blend `filtered` into `img` weighted by the selection mask (empty mask = take filtered as is).
void applyMasked(Image& img, const Image& filtered, const std::vector<uint8_t>& mask);

}  // namespace ag
