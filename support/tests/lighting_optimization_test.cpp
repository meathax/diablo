// Differential oracle: the runner supplies untouched upstream reference files.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <utility>
#include <cstdio>
#include <stdexcept>
#include <vector>
#include "engine/render/blit_impl.hpp"
#include "reference_blit_impl.hpp"

namespace devilution { uint8_t paletteTransparencyLookup[256][256]; }
using namespace devilution;
using Tables = std::array<std::array<uint8_t, LightTableSize>, NumLightingLevels>;
static void Require(bool condition, const char *message) { if (!condition) throw std::runtime_error(message); }
struct Geometry {
    Point tile {48, 44}, target {0, -17};
    int width = 640, height = 352, rows = 25, columns = 10;
    uint_fast8_t micro = 10;
};
static Tables tables;
static uint8_t lights[MAXDUNX][MAXDUNY];
static std::vector<uint8_t> pixels(2048 * 1024);
static uint8_t *Output() { return pixels.data() + 2048 * 8; }
static auto Build(const Geometry &g) {
    return Lightmap::build(true, g.tile, g.target, g.width, g.height, g.rows, g.columns,
        Output(), g.width, tables, tables[0].data(), tables.back().data(), lights, g.micro);
}
static auto Reference(const Geometry &g) {
    return ReferenceLightmap::build(true, g.tile, g.target, g.width, g.height, g.rows, g.columns,
        Output(), g.width, tables, tables[0].data(), tables.back().data(), lights, g.micro);
}
static void CompareMaps(const Geometry &g) {
    auto actual = Build(g);
    auto expected = Reference(g);
    const int height = g.height + 32 * (g.micro / 2 + 1);
    for (int y = -2; y < height; ++y) {
        const auto *where = Output() + y * g.width;
        const auto *a = actual.getLightingAt(where);
        const auto *b = expected.getLightingAt(where);
        Require(std::equal(a, a + g.width, b), "generated lightmap differs");
    }
    for (Point position : {Point{40, 80}, Point{620, 90}, Point{-8, 90}, Point{200, 0}}) {
        std::array<uint8_t, 64 * 32> a {}, b {};
        auto bleed = Lightmap::bleedUp(true, actual, position, a);
        auto refBleed = ReferenceLightmap::bleedUp(true, expected, position, b);
        const int x0 = std::max(0, position.x), x1 = std::min(g.width, position.x + 64);
        const int y0 = std::max(0, position.y - 31), y1 = std::min(height - 1, position.y);
        for (int y = y0; y <= y1; ++y) {
            const auto *where = Output() + y * g.width + x0;
            Require(std::equal(bleed.getLightingAt(where), bleed.getLightingAt(where) + x1 - x0,
                refBleed.getLightingAt(where)), "wall bleed differs");
        }
    }
}
static void CheckBlits(const Geometry &g) {
    auto a = Build(g);
    auto b = Reference(g);
    const int offset = 70 * g.width + 2;
    for (unsigned length : {1U, 7U, 31U, 64U, 127U, 1023U, 1024U, 1280U}) {
        if (length + 2 > static_cast<unsigned>(g.width)) continue;
        std::vector<uint8_t> source(length), initial(length), expected(length);
        for (unsigned i = 0; i < length; ++i) { source[i] = (i * 37 + 17) % 256; initial[i] = (i * 19 + 3) % 256; }
        for (int kind = 0; kind < 4; ++kind) {
            auto *dst = Output() + offset;
            std::copy(initial.begin(), initial.end(), dst);
            switch (kind) {
            case 0: reference::BlitPixelsWithLightmap(dst, source.data(), length, b); break;
            case 1: reference::BlitFillWithLightmap(dst, length, 107, b); break;
            case 2: reference::BlitPixelsBlendedWithLightmap(dst, source.data(), length, b); break;
            case 3: reference::BlitFillBlendedWithLightmap(dst, length, 107, b); break;
            }
            std::copy(dst, dst + length, expected.begin());
            std::copy(initial.begin(), initial.end(), dst);
            switch (kind) {
            case 0: BlitPixelsWithLightmap(dst, source.data(), length, a); break;
            case 1: BlitFillWithLightmap(dst, length, 107, a); break;
            case 2: BlitPixelsBlendedWithLightmap(dst, source.data(), length, a); break;
            case 3: BlitFillBlendedWithLightmap(dst, length, 107, a); break;
            }
            Require(std::equal(expected.begin(), expected.end(), dst), "lit/blended pixels differ");
        }
    }
}
static void CheckAddressing() {
    std::vector<uint8_t> buffer(2048 * 256), light(buffer.size());
    for (auto pair : {std::pair{640,640}, std::pair{672,640}, std::pair{640,64}}) {
        const auto *base = buffer.data() + 8192;
        Lightmap a(base, pair.first, light, pair.second, tables, tables[0].data(), tables.back().data());
        ReferenceLightmap b(base, pair.first, light, pair.second, tables, tables[0].data(), tables.back().data());
        for (int i = -4096; i < 640 * 200; ++i)
            Require(a.getLightingAt(base + i) == b.getLightingAt(base + i), "address calculation differs");
    }
}
int main() {
    try {
        for (unsigned l = 0; l < NumLightingLevels; ++l)
            for (unsigned c = 0; c < LightTableSize; ++c) tables[l][c] = (c + l * 7) % 256;
        // Deliberately asymmetric: exchanging blend operands must fail.
        for (unsigned a = 0; a < 256; ++a) for (unsigned b = 0; b < 256; ++b)
            paletteTransparencyLookup[a][b] = (a * 3 + b * 7) % 256;
        CheckAddressing();
        Geometry g;
        auto uniform = Build(g);
        Require(uniform.uniformLightTable() != nullptr && uniform.uniformLightIsIdentity(), "town uniform fast path absent");
        auto builds = Lightmap::buildCountForTesting();
        CompareMaps(g); CheckBlits(g);
        Require(Lightmap::buildCountForTesting() == builds, "unchanged lighting was rebuilt");
        tables[0][19] ^= 0x7F;
        Require(!Build(g).uniformLightIsIdentity(), "changed LUT retained identity flag");
        CheckBlits(g);
        Require(Lightmap::buildCountForTesting() == builds, "palette unnecessarily invalidates light levels");
        auto toggledOff = Lightmap::build(false, g.tile, g.target, g.width, g.height, g.rows, g.columns,
            Output(), g.width, tables, tables[0].data(), tables.back().data(), lights, g.micro);
        Require(toggledOff.uniformLightTable() == nullptr, "lighting-off metadata leaked");
        CompareMaps(g);
        for (unsigned level : {3U, 15U}) {
            std::memset(lights, level, sizeof(lights));
            CompareMaps(g); CheckBlits(g);
        }
        Geometry wide = g; wide.width = 1536; wide.columns = 28;
        std::memset(lights, 0, sizeof(lights));
        CompareMaps(wide); CheckBlits(wide);
        uint32_t rng = 1234;
        for (auto &row : lights) for (auto &cell : row) { rng = rng * 1664525U + 1013904223U; cell = (rng >> 24) & 15; }
        CompareMaps(g); CheckBlits(g);
        Require(Build(g).uniformLightTable() == nullptr, "mixed light classified uniform");
        for (int input = 0; input < 9; ++input) {
            builds = Lightmap::buildCountForTesting();
            switch (input) {
            case 0: lights[48][44] ^= 1; break;
            case 1: ++g.tile.x; break;
            case 2: ++g.target.x; break;
            case 3: g.width += 32; break;
            case 4: g.height += 16; break;
            case 5: ++g.rows; break;
            case 6: ++g.columns; break;
            case 7: g.micro += 2; break;
            case 8: ++g.tile.y; ++g.target.y; break;
            }
            CompareMaps(g);
            Require(Lightmap::buildCountForTesting() == builds + 1, "cache input did not invalidate exactly once");
        }
        g.tile = {0, 0}; CompareMaps(g);
        std::puts("PASS: lightmap/bleed/blit equality, addressing, uniform tables, cache reuse and invalidation");
        return 0;
    } catch (const std::exception &e) { std::fprintf(stderr, "FAIL: %s\n", e.what()); return 1; }
}
