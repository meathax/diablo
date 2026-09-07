#include "../reference/indexed_frame.hpp"
#include <array>
#include <fstream>
#include <sstream>
#include <vector>

int main(int argc, char **argv)
{
    if (argc != 2) return 1;
    constexpr std::size_t Pitch = 656;
    std::vector<std::uint8_t> pixels(Pitch * 480, 0xee);
    std::array<std::uint8_t, 768> palette {};
    for (std::size_t y = 0; y < 480; ++y)
        for (std::size_t x = 0; x < 640; ++x)
            pixels[y * Pitch + x] = static_cast<std::uint8_t>((x + y) % 255);
    // Entry 255 is deliberately unused in the pixels; it must still be captured.
    for (std::size_t i = 0; i < palette.size(); ++i)
        palette[i] = static_cast<std::uint8_t>(i);
    std::ostringstream rejected;
    if (diablo_reference::WriteIndexedFrame(rejected, pixels, 639, palette, 7, 350)
        || diablo_reference::WriteIndexedFrame(rejected, std::span(pixels).first(100), Pitch, palette, 7, 350)
        || diablo_reference::WriteIndexedFrame(rejected, pixels, Pitch, std::span(palette).first(767), 7, 350)
        || !rejected.str().empty()) return 2;
    std::ofstream out(argv[1], std::ios::binary);
    return diablo_reference::WriteIndexedFrame(out, pixels, Pitch, palette, 7, 350) ? 0 : 3;
}
