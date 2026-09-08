#pragma once

#include "indexed_frame.hpp"
#include "engine/surface.hpp"
#include "levels/gendung.h"
#include "player.h"
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>

namespace diablo_reference {

inline std::uint64_t CaptureStartLogicMs()
{
    static const std::uint64_t value = [] {
        const char *text = std::getenv("DIABLO_CAPTURE_START_MS");
        if (text == nullptr || *text == '\0') return std::uint64_t { 0 };
        char *end = nullptr;
        const auto parsed = std::strtoull(text, &end, 10);
        if (end == text || *end != '\0') std::abort();
        return static_cast<std::uint64_t>(parsed);
    }();
    return value;
}

// Called only after the complete indexed gameplay draw, before presentation.
// Capture runs intentionally perform disk I/O and must not be used for FPS claims.
inline void CaptureRenderedFrame(const devilution::Surface &frame, std::uint64_t logicMs)
{
    static const char *directory = std::getenv("DIABLO_CAPTURE_DIR");
    if (directory == nullptr || *directory == '\0') return;
    if (logicMs < CaptureStartLogicMs()) return;
    const char *scenario = std::getenv("DIABLO_NATIVE_SCENARIO");
    const bool dungeon = scenario != nullptr && std::strcmp(scenario, "dungeon-v1") == 0;
    if (dungeon && (devilution::currlevel != 1 || devilution::MyPlayer == nullptr
        || !devilution::MyPlayer->plractive || devilution::MyPlayer->plrlevel != 1
        || devilution::MyPlayer->_pmode == devilution::PM_NEWLVL)) return;
    static std::uint64_t frameNumber = 0;
    const auto id = frameNumber++;
    if (id % 128 != 0) return;
    const auto fail = [] { std::fputs("Host indexed capture failed\n", stderr); std::abort(); };
    auto *surface = frame.surface;
    if (surface == nullptr || surface->format == nullptr || surface->pixels == nullptr
        || frame.w() != 640 || frame.h() != 480 || surface->format->BytesPerPixel != 1
        || surface->format->palette == nullptr || surface->format->palette->ncolors != 256
        || frame.region.x < 0 || frame.region.y < 0
        || frame.region.x + 640 > surface->w || frame.region.y + 480 > surface->h
        || surface->pitch < frame.region.x + 640)
        fail();
    std::array<std::uint8_t, 768> rgb {};
    for (std::size_t i = 0; i < 256; ++i) {
        const auto color = surface->format->palette->colors[i];
        rgb[3 * i] = color.r;
        rgb[3 * i + 1] = color.g;
        rgb[3 * i + 2] = color.b;
    }
    const std::filesystem::path folder(directory);
    std::error_code error;
    std::filesystem::create_directories(folder, error);
    if (error) fail();
    const auto path = folder / ("frame-" + std::to_string(id) + ".d8f");
    if (std::filesystem::exists(path, error) || error) fail();
    auto temporary = path;
    temporary += ".partial";
    if (std::filesystem::exists(temporary, error) || error) fail();
    std::ofstream output(temporary, std::ios::binary);
    const std::size_t bytes = static_cast<std::size_t>(surface->pitch) * 479 + 640;
    if (!WriteIndexedFrame(output, {frame.at(0, 0), bytes}, surface->pitch, rgb, id, logicMs)) fail();
    output.close();
    if (!output) fail();
    std::filesystem::rename(temporary, path, error);
    if (error) fail();
    if (dungeon) {
        const std::filesystem::path statePath(path.string() + ".state.json");
        const std::filesystem::path stateTemporary(statePath.string() + ".partial");
        if (std::filesystem::exists(statePath, error) || error
            || std::filesystem::exists(stateTemporary, error) || error) fail();
        std::ofstream state(stateTemporary);
        state << "{\"schema\":\"diablo-capture-scene-state-v1\",\"frame\":" << id
              << ",\"logic_ms\":" << logicMs << ",\"level\":" << unsigned(devilution::currlevel)
              << ",\"player_level\":" << unsigned(devilution::MyPlayer->plrlevel)
              << ",\"player_active\":true,\"transition_complete\":true}\n";
        state.close();
        if (!state) fail();
        std::filesystem::rename(stateTemporary, statePath, error);
        if (error) fail();
    }
}

} // namespace diablo_reference
