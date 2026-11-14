#pragma once
#include <map>
#include <string>
#include <vector>
#include "common/types.h"
#include "loader/elf.h"

namespace Core {

struct ImportStats {
    u32 resolved = 0;
    u32 stubbed = 0;
};

// One loaded ELF module (the game's eboot.bin or a .prx library) in host memory.
class Module {
public:
    bool Load(const Loader::ElfFile& elf, std::string& error);
    void PrintInfo() const;

    u8* Base() const { return base_; }
    u64 Size() const { return size_; }
    VAddr EntryPoint() const { return entry_; }
    const ImportStats& Stats() const { return stats_; }

private:
    bool MapSegments(const Loader::ElfFile& elf, std::string& error);
    bool ParseDynamic(const Loader::ElfFile& elf, std::string& error);
    bool ApplyRelocations(const Loader::Elf64Rela* relas, u64 count, std::string& error);
    u64 ResolveImport(const std::string& encoded_name);

    const char* String(u32 offset) const;

    u8* base_ = nullptr;
    u64 size_ = 0;
    u64 load_bias_ = 0; // host address minus ELF vaddr
    VAddr entry_ = 0;
    std::vector<Loader::Elf64Phdr> phdrs_;
    bool sce_dynamic_ = false;

    // Dynamic linking info (pointers into host memory)
    const char* strtab_ = nullptr;
    u64 strsz_ = 0;
    const Loader::Elf64Sym* symtab_ = nullptr;
    u64 symcount_ = 0;
    std::vector<std::string> needed_;
    std::map<u16, std::string> import_modules_;
    std::map<u16, std::string> import_libraries_;
    ImportStats stats_;
};

// Calls the guest entry point the way the PS4/PS5 kernel does.
int RunEntry(const Module& module, const std::string& program_name);

} // namespace Core
