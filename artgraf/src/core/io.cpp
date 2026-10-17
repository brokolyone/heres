#include "io.h"

#include <cctype>
#include <cstdio>
#include <cstring>
#include <stdexcept>

#include <miniz.h>
#include <nlohmann/json.hpp>

#define STB_IMAGE_IMPLEMENTATION
#include <stb_image.h>
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb_image_write.h>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace ag {

namespace {

FILE* openUtf8(const std::string& path, const char* mode) {
#ifdef _WIN32
    auto widen = [](const std::string& s) {
        int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, nullptr, 0);
        std::wstring w(size_t(n > 0 ? n : 1), L'\0');
        MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, w.data(), n);
        return w;
    };
    return _wfopen(widen(path).c_str(), widen(mode).c_str());
#else
    return std::fopen(path.c_str(), mode);
#endif
}

void appendBytes(void* ctx, void* data, int size) {
    auto* v = static_cast<std::vector<uint8_t>*>(ctx);
    v->insert(v->end(), static_cast<uint8_t*>(data), static_cast<uint8_t*>(data) + size);
}

Image onWhite(const Image& img) {
    Image out(img.w, img.h, {255, 255, 255, 255});
    out.drawOver(img, 0, 0);
    return out;
}

}  // namespace

bool readFile(const std::string& path, std::vector<uint8_t>& out) {
    FILE* f = openUtf8(path, "rb");
    if (!f) return false;
    std::fseek(f, 0, SEEK_END);
    long n = std::ftell(f);
    std::fseek(f, 0, SEEK_SET);
    out.resize(n > 0 ? size_t(n) : 0);
    bool ok = out.empty() || std::fread(out.data(), 1, out.size(), f) == out.size();
    std::fclose(f);
    return ok;
}

bool writeFile(const std::string& path, const std::vector<uint8_t>& data) {
    FILE* f = openUtf8(path, "wb");
    if (!f) return false;
    bool ok = data.empty() || std::fwrite(data.data(), 1, data.size(), f) == data.size();
    ok = std::fclose(f) == 0 && ok;
    return ok;
}

std::string fileName(const std::string& path) {
    size_t p = path.find_last_of("/\\");
    return p == std::string::npos ? path : path.substr(p + 1);
}

std::string fileStem(const std::string& path) {
    std::string n = fileName(path);
    size_t d = n.find_last_of('.');
    return d == std::string::npos || d == 0 ? n : n.substr(0, d);
}

std::string lowerExt(const std::string& path) {
    std::string n = fileName(path);
    size_t d = n.find_last_of('.');
    if (d == std::string::npos) return {};
    std::string e = n.substr(d + 1);
    for (auto& c : e) c = char(std::tolower(uint8_t(c)));
    return e;
}

bool decodeImage(const std::vector<uint8_t>& bytes, Image& out, std::string& err) {
    int w, h, n;
    uint8_t* data = stbi_load_from_memory(bytes.data(), int(bytes.size()), &w, &h, &n, 4);
    if (!data) {
        err = std::string("Не удалось прочитать изображение: ") + stbi_failure_reason();
        return false;
    }
    out = Image(w, h);
    std::memcpy(out.px.data(), data, out.px.size());
    stbi_image_free(data);
    return true;
}

bool loadImage(const std::string& path, Image& out, std::string& err) {
    std::vector<uint8_t> bytes;
    if (!readFile(path, bytes)) {
        err = "Не удалось открыть файл: " + path;
        return false;
    }
    return decodeImage(bytes, out, err);
}

std::vector<uint8_t> encodePng(const Image& img) {
    std::vector<uint8_t> out;
    stbi_write_png_to_func(appendBytes, &out, img.w, img.h, 4, img.px.data(), img.w * 4);
    return out;
}

bool saveImage(const std::string& path, const Image& img, int quality, std::string& err) {
    std::string ext = lowerExt(path);
    std::vector<uint8_t> out;
    int ok = 0;
    if (ext == "png") {
        out = encodePng(img);
        ok = !out.empty();
    } else if (ext == "jpg" || ext == "jpeg") {
        Image flat = onWhite(img);
        ok = stbi_write_jpg_to_func(appendBytes, &out, flat.w, flat.h, 4, flat.px.data(), quality);
    } else if (ext == "bmp") {
        Image flat = onWhite(img);
        ok = stbi_write_bmp_to_func(appendBytes, &out, flat.w, flat.h, 4, flat.px.data());
    } else if (ext == "tga") {
        ok = stbi_write_tga_to_func(appendBytes, &out, img.w, img.h, 4, img.px.data());
    } else {
        err = "Неизвестный формат: ." + ext + " (поддерживаются png, jpg, bmp, tga)";
        return false;
    }
    if (!ok || !writeFile(path, out)) {
        err = "Не удалось записать файл: " + path;
        return false;
    }
    return true;
}

bool saveProject(const std::string& path, const Document& doc, std::string& err) {
    nlohmann::json j;
    j["format"] = "artgraf";
    j["version"] = 1;
    j["width"] = doc.w;
    j["height"] = doc.h;
    j["active"] = doc.active;
    j["layers"] = nlohmann::json::array();

    mz_zip_archive zip{};
    if (!mz_zip_writer_init_heap(&zip, 0, 0)) {
        err = "Ошибка архива";
        return false;
    }
    bool ok = true;
    for (size_t i = 0; i < doc.layers.size() && ok; i++) {
        const Layer& l = doc.layers[i];
        std::string file = "layers/" + std::to_string(i) + ".png";
        std::vector<uint8_t> png = encodePng(l.img);
        ok = mz_zip_writer_add_mem(&zip, file.c_str(), png.data(), png.size(), MZ_NO_COMPRESSION);
        j["layers"].push_back({{"name", l.name}, {"file", file}, {"visible", l.visible},
                               {"opacity", l.opacity}, {"blend", blendId(l.blend)}});
    }
    std::string meta = j.dump(2);
    ok = ok && mz_zip_writer_add_mem(&zip, "project.json", meta.data(), meta.size(), MZ_DEFAULT_COMPRESSION);
    void* buf = nullptr;
    size_t size = 0;
    ok = ok && mz_zip_writer_finalize_heap_archive(&zip, &buf, &size);
    if (ok) {
        std::vector<uint8_t> bytes(static_cast<uint8_t*>(buf), static_cast<uint8_t*>(buf) + size);
        ok = writeFile(path, bytes);
        if (!ok) err = "Не удалось записать файл: " + path;
    } else {
        err = "Ошибка при упаковке проекта";
    }
    mz_zip_writer_end(&zip);
    return ok;
}

bool loadProject(const std::string& path, Document& doc, std::string& err) {
    std::vector<uint8_t> bytes;
    if (!readFile(path, bytes)) {
        err = "Не удалось открыть файл: " + path;
        return false;
    }
    mz_zip_archive zip{};
    if (!mz_zip_reader_init_mem(&zip, bytes.data(), bytes.size(), 0)) {
        err = "Файл повреждён или это не проект ArtGraf";
        return false;
    }
    auto extract = [&](const std::string& name, std::vector<uint8_t>& out) {
        size_t n = 0;
        void* p = mz_zip_reader_extract_file_to_heap(&zip, name.c_str(), &n, 0);
        if (!p) return false;
        out.assign(static_cast<uint8_t*>(p), static_cast<uint8_t*>(p) + n);
        mz_free(p);
        return true;
    };

    bool ok = false;
    try {
        std::vector<uint8_t> meta;
        if (!extract("project.json", meta)) throw std::runtime_error("нет project.json");
        auto j = nlohmann::json::parse(meta.begin(), meta.end());
        if (j.value("format", "") != "artgraf") throw std::runtime_error("неизвестный формат");
        Document d;
        d.w = j.at("width").get<int>();
        d.h = j.at("height").get<int>();
        if (d.w <= 0 || d.h <= 0 || d.w > 30000 || d.h > 30000) throw std::runtime_error("неверный размер");
        for (auto& jl : j.at("layers")) {
            Layer l;
            l.name = jl.value("name", "Слой");
            l.visible = jl.value("visible", true);
            l.opacity = jl.value("opacity", 1.f);
            l.blend = blendFromId(jl.value("blend", "normal").c_str());
            std::vector<uint8_t> png;
            std::string e;
            if (!extract(jl.at("file").get<std::string>(), png) || !decodeImage(png, l.img, e))
                throw std::runtime_error("не читается слой «" + l.name + "»");
            if (l.img.w != d.w || l.img.h != d.h) {
                Image fixed(d.w, d.h);
                fixed.blit(l.img, 0, 0);
                l.img = std::move(fixed);
            }
            d.layers.push_back(std::move(l));
        }
        if (d.layers.empty()) throw std::runtime_error("нет слоёв");
        d.active = std::clamp(j.value("active", 0), 0, int(d.layers.size()) - 1);
        d.sel.reset(d.w, d.h);
        d.path = path;
        d.title = fileStem(path);
        doc = std::move(d);
        ok = true;
    } catch (const std::exception& e) {
        err = std::string("Не удалось открыть проект: ") + e.what();
    }
    mz_zip_reader_end(&zip);
    return ok;
}

}  // namespace ag
