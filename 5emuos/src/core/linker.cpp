#include "core/linker.h"

#include <cstring>
#include <deque>
#include <unordered_map>
#include "common/log.h"
#include "core/memory.h"
#include "core/nid.h"
#include "hle/symbols.h"

namespace Core {
using namespace Loader;

namespace {

// Standard dynamic tags
constexpr s64 DT_NULL = 0, DT_NEEDED = 1, DT_PLTRELSZ = 2, DT_STRTAB = 5, DT_SYMTAB = 6,
              DT_RELA = 7, DT_RELASZ = 8, DT_STRSZ = 10, DT_SYMENT = 11, DT_JMPREL = 23;
// Sony dynamic tags: values are offsets into the PT_SCE_DYNLIBDATA segment.
constexpr s64 DT_SCE_NEEDED_MODULE = 0x6100000F, DT_SCE_IMPORT_LIB = 0x61000015,
              DT_SCE_JMPREL = 0x61000029, DT_SCE_PLTRELSZ = 0x6100002D,
              DT_SCE_RELA = 0x6100002F, DT_SCE_RELASZ = 0x61000031,
              DT_SCE_STRTAB = 0x61000035, DT_SCE_STRSZ = 0x61000037,
              DT_SCE_SYMTAB = 0x61000039, DT_SCE_SYMTABSZ = 0x6100003F;

constexpr u32 R_X86_64_NONE = 0, R_X86_64_64 = 1, R_X86_64_GLOB_DAT = 6,
              R_X86_64_JUMP_SLOT = 7, R_X86_64_RELATIVE = 8;

// ---- Stubs for functions we don't implement yet -----------------------------
// Each unresolved import gets a tiny generated trampoline that remembers which
// function it stands for, logs the call, and returns 0. This lets a game run as
// far as possible and tells us exactly what to implement next.
struct StubInfo {
    std::string nid;
    std::string name;
    std::string library;
    u64 calls = 0;
};

u64 PS5_SYSV_ABI UnimplementedFunction(StubInfo* info) {
    if (info->calls++ < 3) {
        LOG_WARNING("HLE", "Unimplemented: {} ({}) from {}", info->name, info->nid, info->library);
    }
    return 0;
}

class StubAllocator {
public:
    u64 Create(StubInfo info) {
        infos_.push_back(std::move(info));
        StubInfo* ptr = &infos_.back();
        constexpr u64 kStubSize = 32;
        if (!page_ || used_ + kStubSize > kPage) {
            page_ = static_cast<u8*>(Memory::Allocate(kPage));
            used_ = 0;
        }
        u8* code = page_ + used_;
        used_ += kStubSize;
        const u64 info_addr = reinterpret_cast<u64>(ptr);
        const u64 handler = reinterpret_cast<u64>(&UnimplementedFunction);
        size_t i = 0;
        code[i++] = 0x48; code[i++] = 0xBF; // mov rdi, imm64
        std::memcpy(code + i, &info_addr, 8); i += 8;
        code[i++] = 0x48; code[i++] = 0xB8; // mov rax, imm64
        std::memcpy(code + i, &handler, 8); i += 8;
        code[i++] = 0xFF; code[i++] = 0xE0; // jmp rax
        return reinterpret_cast<u64>(code);
    }

private:
    static constexpr u64 kPage = 0x10000;
    std::deque<StubInfo> infos_; // deque: stable addresses
    u8* page_ = nullptr;
    u64 used_ = 0;
};

StubAllocator g_stubs;
std::unordered_map<std::string, u64> g_stub_cache;

} // namespace

const char* Module::String(u32 offset) const {
    return (strtab_ && offset < strsz_) ? strtab_ + offset : "<bad string>";
}

bool Module::Load(const ElfFile& elf, std::string& error) {
    phdrs_ = elf.ProgramHeaders();
    if (!MapSegments(elf, error)) return false;
    if (!ParseDynamic(elf, error)) return false;
    entry_ = elf.Header().entry + load_bias_;
    return true;
}

bool Module::MapSegments(const ElfFile& elf, std::string& error) {
    u64 lo = ~u64{0}, hi = 0;
    for (const auto& ph : phdrs_) {
        if (ph.type != PT_LOAD && ph.type != PT_SCE_RELRO) continue;
        lo = std::min(lo, Memory::AlignDown(ph.vaddr, Memory::kPageSize));
        hi = std::max(hi, Memory::AlignUp(ph.vaddr + ph.memsz, Memory::kPageSize));
    }
    if (lo >= hi) {
        error = "no loadable segments";
        return false;
    }
    size_ = hi - lo;

    const u16 type = elf.Header().type;
    const bool fixed = (type == ET_EXEC || type == ET_SCE_EXEC);
    base_ = static_cast<u8*>(Memory::Allocate(size_, fixed ? lo : 0));
    if (!base_) {
        error = fixed ? std::format("cannot map fixed address 0x{:x}", lo) : "out of memory";
        return false;
    }
    load_bias_ = reinterpret_cast<u64>(base_) - lo;

    for (const auto& ph : phdrs_) {
        if (ph.type != PT_LOAD && ph.type != PT_SCE_RELRO) continue;
        u8* dst = reinterpret_cast<u8*>(ph.vaddr + load_bias_);
        std::memcpy(dst, elf.Data().data() + ph.offset, ph.filesz);
        // Remainder (memsz > filesz, i.e. .bss) is already zeroed by the allocator.
    }
    // TODO: apply per-segment protection (R/X vs R/W) instead of RWX everywhere.
    return true;
}

bool Module::ParseDynamic(const ElfFile& elf, std::string& error) {
    const Elf64Phdr* dyn_ph = nullptr;
    const Elf64Phdr* dynlib_ph = nullptr;
    for (const auto& ph : phdrs_) {
        if (ph.type == PT_DYNAMIC) dyn_ph = &ph;
        if (ph.type == PT_SCE_DYNLIBDATA) dynlib_ph = &ph;
    }
    if (!dyn_ph) {
        LOG_INFO("Linker", "No PT_DYNAMIC: statically linked module");
        return true;
    }

    // In Sony ELFs the dynamic section and dynlib data are file-only segments.
    const u8* file = elf.Data().data();
    const auto* dyn = reinterpret_cast<const Elf64Dyn*>(file + dyn_ph->offset);
    const u64 dyn_count = dyn_ph->filesz / sizeof(Elf64Dyn);
    const u8* dynlib = dynlib_ph ? file + dynlib_ph->offset : nullptr;

    // Address of a structure referenced by a dynamic tag.
    auto sce_ptr = [&](u64 offset) -> const u8* { return dynlib ? dynlib + offset : nullptr; };
    auto vaddr_ptr = [&](u64 vaddr) -> const u8* { return reinterpret_cast<const u8*>(vaddr + load_bias_); };

    const Elf64Rela* rela = nullptr;
    const Elf64Rela* jmprel = nullptr;
    u64 relasz = 0, pltrelsz = 0, symtabsz = 0;
    std::vector<u64> needed_offsets, module_values, library_values;

    for (u64 i = 0; i < dyn_count && dyn[i].tag != DT_NULL; ++i) {
        const u64 v = dyn[i].value;
        switch (dyn[i].tag) {
        case DT_SCE_STRTAB: sce_dynamic_ = true; strtab_ = reinterpret_cast<const char*>(sce_ptr(v)); break;
        case DT_SCE_STRSZ: strsz_ = v; break;
        case DT_SCE_SYMTAB: symtab_ = reinterpret_cast<const Elf64Sym*>(sce_ptr(v)); break;
        case DT_SCE_SYMTABSZ: symtabsz = v; break;
        case DT_SCE_RELA: rela = reinterpret_cast<const Elf64Rela*>(sce_ptr(v)); break;
        case DT_SCE_RELASZ: relasz = v; break;
        case DT_SCE_JMPREL: jmprel = reinterpret_cast<const Elf64Rela*>(sce_ptr(v)); break;
        case DT_SCE_PLTRELSZ: pltrelsz = v; break;
        case DT_SCE_NEEDED_MODULE: module_values.push_back(v); break;
        case DT_SCE_IMPORT_LIB: library_values.push_back(v); break;
        // Plain ELF (homebrew built with a standard toolchain, or our tests):
        case DT_STRTAB: if (!strtab_) strtab_ = reinterpret_cast<const char*>(vaddr_ptr(v)); break;
        case DT_STRSZ: if (!strsz_) strsz_ = v; break;
        case DT_SYMTAB: if (!symtab_) symtab_ = reinterpret_cast<const Elf64Sym*>(vaddr_ptr(v)); break;
        case DT_RELA: if (!rela) rela = reinterpret_cast<const Elf64Rela*>(vaddr_ptr(v)); break;
        case DT_RELASZ: if (!relasz) relasz = v; break;
        case DT_JMPREL: if (!jmprel) jmprel = reinterpret_cast<const Elf64Rela*>(vaddr_ptr(v)); break;
        case DT_PLTRELSZ: if (!pltrelsz) pltrelsz = v; break;
        case DT_NEEDED: needed_offsets.push_back(v); break;
        default: break;
        }
    }
    if (sce_dynamic_ && !dynlib) {
        error = "SCE dynamic tags present but no PT_SCE_DYNLIBDATA segment";
        return false;
    }

    for (u64 off : needed_offsets) needed_.emplace_back(String(static_cast<u32>(off)));
    // Module/library value layout: low 32 bits = name offset, top 16 bits = id.
    for (u64 v : module_values) import_modules_[static_cast<u16>(v >> 48)] = String(static_cast<u32>(v));
    for (u64 v : library_values) import_libraries_[static_cast<u16>(v >> 48)] = String(static_cast<u32>(v));

    if (symtab_) {
        // Plain ELFs don't record symtab size; the largest symbol index used by a
        // relocation is enough for bounds checking.
        symcount_ = symtabsz ? symtabsz / sizeof(Elf64Sym) : ~u64{0};
    }

    if (rela && !ApplyRelocations(rela, relasz / sizeof(Elf64Rela), error)) return false;
    if (jmprel && !ApplyRelocations(jmprel, pltrelsz / sizeof(Elf64Rela), error)) return false;
    return true;
}

u64 Module::ResolveImport(const std::string& encoded_name) {
    const auto parsed = Nid::Parse(encoded_name);
    // Real PS4/PS5 symbols are already NIDs ("xxxxxxxxxxx#L#M"). Plain homebrew
    // ELFs may import by real name, so hash those ourselves.
    const std::string nid = parsed.has_ids ? parsed.nid : Nid::FromName(parsed.nid);

    std::string library = "?";
    if (parsed.has_ids) {
        if (auto it = import_libraries_.find(parsed.library_id); it != import_libraries_.end()) {
            library = it->second;
        }
    }

    if (const auto* sym = HLE::FindByNid(nid)) {
        ++stats_.resolved;
        LOG_DEBUG("Linker", "Resolved {} -> HLE {}::{}", encoded_name, sym->library, sym->name);
        return reinterpret_cast<u64>(sym->address);
    }

    ++stats_.stubbed;
    if (auto it = g_stub_cache.find(nid); it != g_stub_cache.end()) return it->second;
    std::string name = parsed.has_ids ? HLE::NameForNid(nid) : parsed.nid;
    LOG_DEBUG("Linker", "Stubbing {} ({}) from {}", name, nid, library);
    const u64 stub = g_stubs.Create(StubInfo{nid, name, library});
    g_stub_cache[nid] = stub;
    return stub;
}

bool Module::ApplyRelocations(const Elf64Rela* relas, u64 count, std::string& error) {
    for (u64 i = 0; i < count; ++i) {
        const auto& r = relas[i];
        const u32 type = static_cast<u32>(r.info);
        const u32 sym_index = static_cast<u32>(r.info >> 32);
        u64* target = reinterpret_cast<u64*>(r.offset + load_bias_);

        auto symbol_value = [&](u64& out) -> bool {
            if (!symtab_ || sym_index >= symcount_) {
                error = std::format("relocation {} references bad symbol {}", i, sym_index);
                return false;
            }
            const auto& sym = symtab_[sym_index];
            if (sym.shndx != 0) { // defined in this module
                out = sym.value + load_bias_;
            } else {
                out = ResolveImport(String(sym.name));
            }
            return true;
        };

        u64 s = 0;
        switch (type) {
        case R_X86_64_NONE:
            break;
        case R_X86_64_RELATIVE:
            *target = load_bias_ + r.addend;
            break;
        case R_X86_64_64:
            if (!symbol_value(s)) return false;
            *target = s + r.addend;
            break;
        case R_X86_64_GLOB_DAT:
        case R_X86_64_JUMP_SLOT:
            if (!symbol_value(s)) return false;
            *target = s;
            break;
        default:
            // TODO: TLS relocations (DTPMOD64/DTPOFF64/TPOFF64) once TLS is emulated.
            LOG_WARNING("Linker", "Unhandled relocation type {} at 0x{:x}", type, r.offset);
            break;
        }
    }
    return true;
}

void Module::PrintInfo() const {
    LOG_INFO("Linker", "Loaded at 0x{:x}, size 0x{:x}, entry 0x{:x}, {} dynamic info",
             reinterpret_cast<u64>(base_), size_, entry_, sce_dynamic_ ? "SCE" : "standard");
    for (const auto& [id, name] : import_modules_) LOG_INFO("Linker", "  needs module [{}] {}", id, name);
    for (const auto& [id, name] : import_libraries_) LOG_INFO("Linker", "  imports library [{}] {}", id, name);
    for (const auto& name : needed_) LOG_INFO("Linker", "  DT_NEEDED {}", name);
    LOG_INFO("Linker", "Imports: {} implemented, {} stubbed", stats_.resolved, stats_.stubbed);
}

// ---- Entry -------------------------------------------------------------------
namespace {
// What the kernel passes in rdi to a process's _start.
struct EntryParams {
    s32 argc;
    u32 padding;
    const char* argv[3];
};

void PS5_SYSV_ABI ProgramExitHandler() {
    LOG_INFO("Core", "Program exit handler called");
}

using EntryFunc = void PS5_SYSV_ABI (*)(EntryParams*, void (PS5_SYSV_ABI*)());
} // namespace

int RunEntry(const Module& module, const std::string& program_name) {
    EntryParams params{};
    params.argc = 1;
    params.argv[0] = program_name.c_str();
    // TODO: run on a dedicated guest thread with its own stack and TLS (fs base).
    LOG_INFO("Core", "Jumping to guest entry 0x{:x}", module.EntryPoint());
    auto entry = reinterpret_cast<EntryFunc>(module.EntryPoint());
    entry(&params, &ProgramExitHandler);
    LOG_INFO("Core", "Guest entry returned");
    return 0;
}

} // namespace Core
