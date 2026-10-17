#pragma once
#include <cstddef>

// PNG files embedded into the executable at build time (see cmake/embed.cmake).
extern const unsigned char kLogoPng[];
extern const std::size_t kLogoPngSize;
extern const unsigned char kSplashPng[];
extern const std::size_t kSplashPngSize;
