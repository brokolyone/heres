#include "hle/symbols.h"

#include <fstream>
#include <unordered_map>
#include "common/log.h"
#include "core/nid.h"

namespace HLE {
namespace {
std::unordered_map<std::string, Symbol>& Table() {
    static std::unordered_map<std::string, Symbol> table;
    return table;
}
std::unordered_map<std::string, std::string>& NameDb() {
    static std::unordered_map<std::string, std::string> db;
    return db;
}
} // namespace

void Register(std::string_view library, std::string_view name, void* address) {
    const auto nid = Core::Nid::FromName(name);
    Table()[nid] = Symbol{std::string(library), std::string(name), address};
    NameDb()[nid] = std::string(name);
}

const Symbol* FindByNid(std::string_view nid) {
    const auto it = Table().find(std::string(nid));
    return it == Table().end() ? nullptr : &it->second;
}

void RegisterAll() {
    Libc::RegisterFunctions();
    LibKernel::RegisterFunctions();
    LOG_INFO("HLE", "Registered {} HLE functions", Table().size());
}

size_t LoadNameDatabase(const std::string& path) {
    std::ifstream file(path);
    size_t count = 0;
    for (std::string line; std::getline(file, line);) {
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
        if (line.empty() || line[0] == '#') continue;
        NameDb().emplace(Core::Nid::FromName(line), line);
        ++count;
    }
    return count;
}

std::string NameForNid(std::string_view nid) {
    const auto it = NameDb().find(std::string(nid));
    return it == NameDb().end() ? std::string("<unknown name>") : it->second;
}

} // namespace HLE
