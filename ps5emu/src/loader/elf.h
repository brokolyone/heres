#pragma once
#include <filesystem>
#include <string>
#include <vector>
#include "common/types.h"

namespace Loader {

// ELF types. PS4/PS5 use the standard ELF64 container with Sony-specific
// e_type values, program header types and dynamic tags.
enum ElfType : u16 {
    ET_EXEC = 2,
    ET_DYN = 3,
    ET_SCE_EXEC = 0xFE00,
    ET_SCE_DYNEXEC = 0xFE10,
    ET_SCE_DYNAMIC = 0xFE18,
};

enum ProgramType : u32 {
    PT_LOAD = 1,
    PT_DYNAMIC = 2,
    PT_INTERP = 3,
    PT_TLS = 7,
    PT_GNU_EH_FRAME = 0x6474E550,
    PT_SCE_RELA = 0x60000000,
    PT_SCE_DYNLIBDATA = 0x61000000,
    PT_SCE_PROCPARAM = 0x61000001,
    PT_SCE_MODULE_PARAM = 0x61000002,
    PT_SCE_RELRO = 0x61000010,
    PT_SCE_COMMENT = 0x6FFFFF00,
    PT_SCE_VERSION = 0x6FFFFF01,
};

struct Elf64Header {
    u8 ident[16];
    u16 type;
    u16 machine;
    u32 version;
    u64 entry;
    u64 phoff;
    u64 shoff;
    u32 flags;
    u16 ehsize;
    u16 phentsize;
    u16 phnum;
    u16 shentsize;
    u16 shnum;
    u16 shstrndx;
};

struct Elf64Phdr {
    u32 type;
    u32 flags;
    u64 offset;
    u64 vaddr;
    u64 paddr;
    u64 filesz;
    u64 memsz;
    u64 align;
};

struct Elf64Dyn {
    s64 tag;
    u64 value;
};

struct Elf64Sym {
    u32 name;
    u8 info;
    u8 other;
    u16 shndx;
    u64 value;
    u64 size;
};

struct Elf64Rela {
    u64 offset;
    u64 info;
    s64 addend;
};

static_assert(sizeof(Elf64Header) == 64);
static_assert(sizeof(Elf64Phdr) == 56);
static_assert(sizeof(Elf64Sym) == 24);
static_assert(sizeof(Elf64Rela) == 24);

const char* ElfTypeName(u16 type);
const char* ProgramTypeName(u32 type);

class ElfFile {
public:
    // Loads the file into memory and validates headers. Encrypted SELF files
    // (as found on a console) are detected and rejected with a clear message.
    bool Open(const std::filesystem::path& path, std::string& error);

    const Elf64Header& Header() const { return header_; }
    const std::vector<Elf64Phdr>& ProgramHeaders() const { return phdrs_; }
    const std::vector<u8>& Data() const { return data_; }
    const std::filesystem::path& Path() const { return path_; }

    bool IsSceType() const;

private:
    std::filesystem::path path_;
    std::vector<u8> data_;
    Elf64Header header_{};
    std::vector<Elf64Phdr> phdrs_;
};

} // namespace Loader
