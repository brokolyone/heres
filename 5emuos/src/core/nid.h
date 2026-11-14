#pragma once
#include <optional>
#include <string>
#include <string_view>
#include "common/types.h"

// PS4/PS5 binaries do not import functions by name. Each import is a "NID":
// the first 8 bytes of SHA-1(name + salt), encoded as 11 base64 characters.
// Symbol names in the ELF look like "hcuQgD53UxM#A#B" = NID # library id # module id.
namespace Core::Nid {

std::string FromName(std::string_view name);

struct SymbolName {
    std::string nid;
    u16 library_id = 0;
    u16 module_id = 0;
    bool has_ids = false;
};

// Splits "NID#L#M". Plain names (no '#') are returned with has_ids = false.
SymbolName Parse(std::string_view encoded);

// Decodes the custom base64 used for the library/module ids.
std::optional<u16> DecodeId(std::string_view s);

} // namespace Core::Nid
