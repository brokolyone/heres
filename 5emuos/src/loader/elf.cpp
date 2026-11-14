#include "loader/elf.h"

#include <cstring>
#include <fstream>

namespace Loader {

const char* ElfTypeName(u16 type) {
    switch (type) {
    case ET_EXEC: return "ET_EXEC";
    case ET_DYN: return "ET_DYN";
    case ET_SCE_EXEC: return "ET_SCE_EXEC";
    case ET_SCE_DYNEXEC: return "ET_SCE_DYNEXEC";
    case ET_SCE_DYNAMIC: return "ET_SCE_DYNAMIC";
    default: return "unknown";
    }
}

const char* ProgramTypeName(u32 type) {
    switch (type) {
    case PT_LOAD: return "LOAD";
    case PT_DYNAMIC: return "DYNAMIC";
    case PT_INTERP: return "INTERP";
    case PT_TLS: return "TLS";
    case PT_GNU_EH_FRAME: return "GNU_EH_FRAME";
    case PT_SCE_RELA: return "SCE_RELA";
    case PT_SCE_DYNLIBDATA: return "SCE_DYNLIBDATA";
    case PT_SCE_PROCPARAM: return "SCE_PROCPARAM";
    case PT_SCE_MODULE_PARAM: return "SCE_MODULE_PARAM";
    case PT_SCE_RELRO: return "SCE_RELRO";
    case PT_SCE_COMMENT: return "SCE_COMMENT";
    case PT_SCE_VERSION: return "SCE_VERSION";
    default: return "?";
    }
}

bool ElfFile::IsSceType() const {
    return header_.type == ET_SCE_EXEC || header_.type == ET_SCE_DYNEXEC ||
           header_.type == ET_SCE_DYNAMIC;
}

bool ElfFile::Open(const std::filesystem::path& path, std::string& error) {
    path_ = path;
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file) {
        error = "cannot open file";
        return false;
    }
    const auto size = static_cast<size_t>(file.tellg());
    file.seekg(0);
    data_.resize(size);
    file.read(reinterpret_cast<char*>(data_.data()), static_cast<std::streamsize>(size));

    if (size < sizeof(Elf64Header)) {
        error = "file too small to be an ELF";
        return false;
    }

    // Signed/encrypted SELF containers (PS4: 4F 15 3D 1D, PS5: 54 14 F5 EE).
    // These must be decrypted on your own console first.
    static constexpr u8 kSelfPs4[4] = {0x4F, 0x15, 0x3D, 0x1D};
    static constexpr u8 kSelfPs5[4] = {0x54, 0x14, 0xF5, 0xEE};
    if (std::memcmp(data_.data(), kSelfPs4, 4) == 0 || std::memcmp(data_.data(), kSelfPs5, 4) == 0) {
        error = "this is an encrypted SELF. Dump a decrypted ELF from your own console first";
        return false;
    }

    std::memcpy(&header_, data_.data(), sizeof(header_));
    if (std::memcmp(header_.ident, "\x7F" "ELF", 4) != 0) {
        error = "not an ELF file (bad magic)";
        return false;
    }
    if (header_.ident[4] != 2 || header_.ident[5] != 1) {
        error = "only little-endian ELF64 is supported";
        return false;
    }
    if (header_.machine != 62) {
        error = "not an x86-64 binary";
        return false;
    }
    if (header_.phentsize != sizeof(Elf64Phdr) ||
        header_.phoff + u64{header_.phnum} * sizeof(Elf64Phdr) > size) {
        error = "program header table is out of bounds";
        return false;
    }

    phdrs_.resize(header_.phnum);
    std::memcpy(phdrs_.data(), data_.data() + header_.phoff, header_.phnum * sizeof(Elf64Phdr));
    for (const auto& ph : phdrs_) {
        if (ph.filesz && ph.offset + ph.filesz > size) {
            error = "segment data is out of bounds (truncated dump?)";
            return false;
        }
    }
    return true;
}

} // namespace Loader
