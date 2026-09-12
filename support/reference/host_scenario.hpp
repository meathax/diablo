#pragma once

#include <cstdlib>
#include <cstring>
#include "DiabloUI/diabloui.h"
#include "diablo.h"
#include "engine/demomode.h"
#include "engine/random.hpp"
#include "menu.h"
#include "pfile.h"
#include "player.h"
#include "utils/log.hpp"

namespace diablo_reference {
inline bool NativeScenarioEnabled()
{
    const char *value = std::getenv("DIABLO_NATIVE_SCENARIO");
    return value != nullptr
        && (std::strcmp(value, "town-v1") == 0 || std::strcmp(value, "dungeon-v1") == 0);
}

inline bool NativeDungeonScenarioEnabled()
{
    const char *value = std::getenv("DIABLO_NATIVE_SCENARIO");
    return value != nullptr && std::strcmp(value, "dungeon-v1") == 0;
}

inline void BeginNativeScenario()
{
    using namespace devilution;
    if (!NativeScenarioEnabled()) return;
    // Only the isolated runner may opt in. Never replace an existing hero.
    if (!demo::IsRunning() || HeadlessMode || gbIsSpawn || gbIsMultiplayer
        || pfile_ui_get_first_unused_save_num() != 0)
        std::abort();
    SetRndSeed(42U);
    _uiheroinfo hero {};
    hero.heroclass = HeroClass::Warrior;
    std::strcpy(hero.name, "Reference");
    gSaveNumber = 0;
    if (!pfile_ui_save_create(&hero)) std::abort();
    gbLoadGame = false;
}

inline void NativeScenarioTick(unsigned ticks)
{
    using namespace devilution;
    if (!NativeDungeonScenarioEnabled() || ticks != 64)
        return;
    if (MyPlayer == nullptr || !MyPlayer->plractive || currlevel != 0)
        std::abort();
    // Use the same level-change path as the real town stair trigger. This keeps
    // save, level generation and player-entry state on the production path.
    StartNewLvl(*MyPlayer, WM_DIABNEXTLVL, 1);
}

inline void FinishNativeScenario(unsigned ticks)
{
    using namespace devilution;
    if (!NativeScenarioEnabled()) return;
    const bool dungeon = NativeDungeonScenarioEnabled();
    const bool valid = ticks == 512 && MyPlayer != nullptr && MyPlayer->plractive
        && MyPlayer->_pHitPoints > 0 && currlevel == (dungeon ? 1 : 0)
        && !HeadlessMode && !gbIsSpawn;
    if (!valid) {
        LogError("Native scenario {} failed: ticks={}, player={}, active={}, hp={}, level={}, headless={}, spawn={}",
            dungeon ? "dungeon-v1" : "town-v1", ticks, MyPlayer != nullptr,
            MyPlayer != nullptr && MyPlayer->plractive,
            MyPlayer != nullptr ? MyPlayer->_pHitPoints : 0, currlevel, HeadlessMode, gbIsSpawn);
        std::abort();
    }
    pfile_write_hero(true);
    LogInfo("Native scenario {} complete: campaign={}, ticks={}, level={}, position={},{}",
        dungeon ? "dungeon-v1" : "town-v1",
        gbIsHellfire ? "hellfire" : "diablo", ticks,
        currlevel,
        MyPlayer->position.tile.x, MyPlayer->position.tile.y);
}
} // namespace diablo_reference
