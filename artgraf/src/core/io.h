#pragma once
#include <string>
#include <vector>

#include "document.h"

namespace ag {

// UTF-8 paths on every platform (on Windows they are converted to wide strings).
bool readFile(const std::string& path, std::vector<uint8_t>& out);
bool writeFile(const std::string& path, const std::vector<uint8_t>& data);

std::string fileName(const std::string& path);     // "C:/a/b.png" -> "b.png"
std::string fileStem(const std::string& path);     // -> "b"
std::string lowerExt(const std::string& path);     // -> "png"

bool decodeImage(const std::vector<uint8_t>& bytes, Image& out, std::string& err);
bool loadImage(const std::string& path, Image& out, std::string& err);
std::vector<uint8_t> encodePng(const Image& img);
// Format is picked from the extension: png, jpg/jpeg, bmp, tga. JPEG/BMP are flattened on white.
bool saveImage(const std::string& path, const Image& img, int jpegQuality, std::string& err);

// .agf project: a zip with project.json and one PNG per layer.
bool saveProject(const std::string& path, const Document& doc, std::string& err);
bool loadProject(const std::string& path, Document& doc, std::string& err);

}  // namespace ag
