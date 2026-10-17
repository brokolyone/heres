#pragma once
#include <string>

namespace ag {

// Platform services that differ on Android (system file picker, photo gallery).
// On desktop these report "not available" and the regular file dialogs are used.
bool platformIsMobile();
bool platformPickFile(bool imagesOnly);         // starts the system picker (asynchronous)
bool platformPollPicked(std::string& path);     // true once the picker finished; empty path = cancelled
bool platformSaveToGallery(const std::string& file, const std::string& displayName, const std::string& mime);
std::string platformDocumentsDir();             // where projects are saved on mobile
std::string platformCacheDir();

}  // namespace ag
