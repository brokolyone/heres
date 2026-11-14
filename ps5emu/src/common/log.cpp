#include "common/log.h"

#include <mutex>

namespace Log {
namespace {
Level g_min_level = Level::Info;
std::mutex g_mutex;

const char* LevelName(Level level) {
    switch (level) {
    case Level::Trace: return "Trace";
    case Level::Debug: return "Debug";
    case Level::Info: return "Info";
    case Level::Warning: return "Warning";
    case Level::Error: return "Error";
    case Level::Critical: return "Critical";
    }
    return "?";
}
} // namespace

void SetMinLevel(Level level) {
    g_min_level = level;
}

void Write(Level level, std::string_view channel, std::string_view message) {
    if (level < g_min_level) {
        return;
    }
    std::scoped_lock lock{g_mutex};
    std::fprintf(stderr, "[%s] <%s> %.*s\n", std::string(channel).c_str(), LevelName(level),
                 static_cast<int>(message.size()), message.data());
}

} // namespace Log
