#include <cstdio>
#include "core/nid.h"

int main() {
    struct Case { const char* name; const char* nid; } cases[] = {
        {"printf", "hcuQgD53UxM"},
        {"puts", "YQ0navp+YIc"},
        {"sceKernelUsleep", "1jfXLRVzisc"},
    };
    int failures = 0;
    for (const auto& c : cases) {
        const auto got = Core::Nid::FromName(c.name);
        if (got != c.nid) {
            std::printf("FAIL %s: expected %s, got %s\n", c.name, c.nid, got.c_str());
            ++failures;
        }
    }
    const auto parsed = Core::Nid::Parse("hcuQgD53UxM#B#C");
    if (!parsed.has_ids || parsed.library_id != 1 || parsed.module_id != 2) {
        std::printf("FAIL parse\n");
        ++failures;
    }
    std::printf(failures ? "nid tests FAILED\n" : "nid tests OK\n");
    return failures ? 1 : 0;
}
