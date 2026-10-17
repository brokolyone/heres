#pragma once
#include "image.h"

namespace ag {

// System clipboard images. Implemented on Windows (PNG and CF_DIB formats); elsewhere these
// return false and the editor falls back to its internal clipboard.
bool clipboardGetImage(Image& out);
bool clipboardSetImage(const Image& img);

}  // namespace ag
