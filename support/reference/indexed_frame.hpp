#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <ostream>
#include <span>

namespace diablo_reference {

// Portable wire format: 32-byte LE header, 256 RGB888 colors, 640x480 indices.
// Row padding is excluded. This capture path is for correctness, not timing runs.
inline bool WriteIndexedFrame(std::ostream &out, std::span<const std::uint8_t> pixels,
    std::size_t pitch, std::span<const std::uint8_t> rgb,
    std::uint64_t frame, std::uint64_t logicMilliseconds)
{
    constexpr std::size_t Width = 640, Height = 480;
    if (rgb.size() != 768 || pitch < Width
        || pixels.size() < Width || pitch > (pixels.size() - Width) / (Height - 1))
        return false;
    std::array<std::uint8_t, 32> header {'D', '8', 'R', 'G', 'B', '0', '0', '1'};
    const auto put = [&](std::size_t offset, std::uint64_t value, int bytes) {
        for (int i = 0; i < bytes; ++i)
            header[offset + i] = static_cast<std::uint8_t>(value >> (i * 8));
    };
    put(8, Width, 4);
    put(12, Height, 4);
    put(16, frame, 8);
    put(24, logicMilliseconds, 8);
    out.write(reinterpret_cast<const char *>(header.data()), header.size());
    out.write(reinterpret_cast<const char *>(rgb.data()), rgb.size());
    for (std::size_t y = 0; y < Height; ++y)
        out.write(reinterpret_cast<const char *>(pixels.data() + y * pitch), Width);
    return static_cast<bool>(out);
}

} // namespace diablo_reference
