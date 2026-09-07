// Regression coverage for the generated Windows host engine fixes.
#include <gtest/gtest.h>
#include <algorithm>
#include <string>
#include "utils/paths.h"
#include "utils/png.h"
#include "utils/sdl_wrap.h"

TEST(HostPngLoading, EmptyPathReturnsNull)
{
    EXPECT_EQ(devilution::LoadPNG(""), nullptr);
}

TEST(HostPngLoading, AbsoluteWindowsPaths)
{
    std::string path = devilution::paths::BasePath()
        + "test/fixtures/text_render_integration_test/basic.png";
    ASSERT_GE(path.size(), 3u);
    ASSERT_EQ(path[1], ':');
    for (char separator : {'/', '\\'}) {
        std::replace(path.begin(), path.end(), '/', separator);
        std::replace(path.begin(), path.end(), '\\', separator);
        devilution::SDLSurfaceUniquePtr surface {devilution::LoadPNG(path.c_str())};
        ASSERT_NE(surface, nullptr) << path << ": " << SDL_GetError();
    }
}
