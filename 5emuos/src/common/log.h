#pragma once
#include <cstdio>
#include <format>
#include <string_view>

namespace Log {

enum class Level { Trace, Debug, Info, Warning, Error, Critical };

void SetMinLevel(Level level);
void Write(Level level, std::string_view channel, std::string_view message);

} // namespace Log

#define PS5_LOG(level, channel, ...) ::Log::Write(::Log::Level::level, channel, std::format(__VA_ARGS__))
#define LOG_TRACE(ch, ...) PS5_LOG(Trace, ch, __VA_ARGS__)
#define LOG_DEBUG(ch, ...) PS5_LOG(Debug, ch, __VA_ARGS__)
#define LOG_INFO(ch, ...) PS5_LOG(Info, ch, __VA_ARGS__)
#define LOG_WARNING(ch, ...) PS5_LOG(Warning, ch, __VA_ARGS__)
#define LOG_ERROR(ch, ...) PS5_LOG(Error, ch, __VA_ARGS__)
#define LOG_CRITICAL(ch, ...) PS5_LOG(Critical, ch, __VA_ARGS__)
