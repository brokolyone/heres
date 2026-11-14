#include <cstdio>
#include <string>
#include "common/log.h"
#include "core/linker.h"
#include "hle/symbols.h"
#include "loader/elf.h"

namespace {
void PrintUsage() {
    std::fprintf(stderr,
                 "5emuos - experimental PS5 emulator\n\n"
                 "Usage: 5emuos [options] <eboot.elf>\n\n"
                 "  --info            only print ELF information, do not run\n"
                 "  --names <file>    symbol name list (one per line) for readable logs\n"
                 "  --debug           verbose logging\n");
}

void PrintElfInfo(const Loader::ElfFile& elf) {
    const auto& h = elf.Header();
    LOG_INFO("Loader", "File: {}", elf.Path().string());
    LOG_INFO("Loader", "Type: {} (0x{:x}), entry 0x{:x}, {} program headers",
             Loader::ElfTypeName(h.type), h.type, h.entry, h.phnum);
    for (const auto& ph : elf.ProgramHeaders()) {
        LOG_INFO("Loader", "  {:<16} vaddr 0x{:010x} filesz 0x{:08x} memsz 0x{:08x} flags {}{}{}",
                 Loader::ProgramTypeName(ph.type), ph.vaddr, ph.filesz, ph.memsz,
                 (ph.flags & 4) ? 'R' : '-', (ph.flags & 2) ? 'W' : '-', (ph.flags & 1) ? 'X' : '-');
    }
}
} // namespace

int main(int argc, char** argv) {
    std::string path, names_file;
    bool info_only = false;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--info") info_only = true;
        else if (arg == "--debug") Log::SetMinLevel(Log::Level::Debug);
        else if (arg == "--names" && i + 1 < argc) names_file = argv[++i];
        else if (arg == "-h" || arg == "--help") { PrintUsage(); return 0; }
        else path = arg;
    }
    if (path.empty()) {
        PrintUsage();
        return 1;
    }

    Loader::ElfFile elf;
    std::string error;
    if (!elf.Open(path, error)) {
        LOG_CRITICAL("Loader", "Failed to open {}: {}", path, error);
        return 1;
    }
    PrintElfInfo(elf);

    HLE::RegisterAll();
    if (!names_file.empty()) {
        LOG_INFO("HLE", "Loaded {} symbol names from {}", HLE::LoadNameDatabase(names_file), names_file);
    }

    Core::Module module;
    if (!module.Load(elf, error)) {
        LOG_CRITICAL("Linker", "Failed to load module: {}", error);
        return 1;
    }
    module.PrintInfo();

    if (info_only) return 0;
    return Core::RunEntry(module, path);
}
