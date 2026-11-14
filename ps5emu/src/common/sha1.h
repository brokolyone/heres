#pragma once
#include <array>
#include <span>
#include "common/types.h"

namespace Common {
std::array<u8, 20> Sha1(std::span<const u8> data);
}
