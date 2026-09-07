#pragma once

#include <cstdlib>
#include <cstring>
#include "DiabloUI/diabloui.h"
#include "diablo.h"
#include "engine/demomode.h"
#include "engine/random.hpp"
#include "game_mode.hpp"
#include "headless_mode.hpp"
#include "menu.h"
#include "pfile.h"
#include "player.h"
#include "utils/log.hpp"

namespace devilution {
extern xoshiro128plusplus seedGenerator;
}

namespace diablo_reference {
inline bool NativeScenarioEnabled()
{
    const char *value = std::getenv("DIABLO_NATIVE_SCENARIO");
    return value != nullptr && std::strcmp(value, "town-v1") == 0;
}

inline void BeginNativeScenario(devilution::GameData *gameData)
{
    using namespace devilution;
    if (!NativeScenarioEnabled()) return;
    // Only the isolated runner may opt in. Never replace an existing hero.
    if (!demo::IsRunning() || HeadlessMode || gbIsSpawn || gbIsMultiplayer
        || pfile_ui_get_first_unused_save_num() != 0)
        std::abort();
    seedGenerator = xoshiro128plusplus(42U);
    xoshiro128plusplus fixedGame(42U);
    fixedGame.save(gameData->gameSeed);
    _uiheroinfo hero {};
    hero.heroclass = HeroClass::Warrior;
    std::strcpy(hero.name, "Reference");
    gSaveNumber = 0;
    if (!pfile_ui_save_create(&hero)) std::abort();
    gbLoadGame = false;
}

inline void FinishNativeScenario(unsigned ticks)
{
    using namespace devilution;
    if (!NativeScenarioEnabled()) return;
    if (ticks != 512 || MyPlayer == nullptr || !MyPlayer->plractive
        || MyPlayer->_pHitPoints <= 0 || currlevel != 0 || HeadlessMode || gbIsSpawn)
        std::abort();
    pfile_write_hero(true);
    LogInfo("Native scenario town-v1 complete: campaign={}, ticks={}, position={},{}",
        gbIsHellfire ? "hellfire" : "diablo", ticks,
        MyPlayer->position.tile.x, MyPlayer->position.tile.y);
}
} // namespace diablo_reference
