#pragma once
#include <imgui.h>

#include "editor.h"

namespace ag {

// Tool icons are drawn with ImDrawList primitives so the app ships no image assets.
void drawToolIcon(ImDrawList* dl, Tool tool, ImVec2 center, float size, ImU32 color);

// The app logo: rounded square with an "A" and a brush stroke.
void drawLogo(ImDrawList* dl, ImVec2 min, float size);

}  // namespace ag
