#pragma once
#include <string>
#include <string_view>
#include "common/types.h"

// Registry of HLE (high-level emulated) system functions, keyed by NID.
namespace HLE {

struct Symbol {
    std::string library; // e.g. "libc", "libkernel"
    std::string name;    // human readable, e.g. "printf"
    void* address = nullptr;
};

void Register(std::string_view library, std::string_view name, void* address);
const Symbol* FindByNid(std::string_view nid);

// Called once at startup; each HLE library registers its functions here.
void RegisterAll();

// Optional: a text file with one known symbol name per line. Lets the logs
// show "sceFooBar" instead of an opaque NID for functions we don't implement yet.
size_t LoadNameDatabase(const std::string& path);
std::string NameForNid(std::string_view nid);

namespace Libc { void RegisterFunctions(); }
namespace LibKernel { void RegisterFunctions(); }

} // namespace HLE

#define HLE_REGISTER(lib, fn) ::HLE::Register(lib, #fn, reinterpret_cast<void*>(&fn))
