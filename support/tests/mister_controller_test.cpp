#include <gtest/gtest.h>

#include <string>
#include <vector>
#include <chrono>
#include <filesystem>

#include "controls/game_controls.h"
#include "controls/padmapper.hpp"
#include "options.h"
#include "utils/paths.h"

namespace devilution {
namespace {

class MisterController : public testing::Test {
protected:
	static inline std::filesystem::path config;
	static void SetUpTestSuite()
	{
		config = std::filesystem::temp_directory_path() / ("diablo-padmap-test-"
		    + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
		ASSERT_TRUE(std::filesystem::create_directory(config));
		paths::SetConfigPath(config.string() + "/");
		LoadOptions();
	}
	static void TearDownTestSuite() { std::filesystem::remove_all(config); }
	static void LoadBindings(PadmapperOptions &pad)
	{
		pad.CommitActions();
		for (auto &action : pad.actions)
			action.LoadFromIni("MisterControllerTest");
	}
};

TEST_F(MisterController, ModifiedActionKeepsItsReleaseAcrossBothReleaseOrders)
{
	for (const bool modifierFirst : { false, true }) {
		PadmapperOptions pad;
		std::vector<std::string> events;
		pad.AddAction("PrimaryAction", "", "", ControllerButton_NONE,
		    [&] { events.emplace_back("attack"); }, [&] { events.emplace_back("attack-up"); });
		pad.AddAction("QuickSpell{}", "", "", ControllerButton_NONE,
		    [&] { events.emplace_back("quick"); }, [&] { events.emplace_back("quick-up"); }, nullptr, 3);
		LoadBindings(pad);
		bool rt = true;
		auto held = [&](ControllerButton b) { return rt && b == ControllerButton_AXIS_TRIGGERRIGHT; };
		const auto *action = pad.findAction(ControllerButton_BUTTON_A, held);
		ASSERT_NE(action, nullptr);
		ASSERT_EQ(action->key, "QuickSpell3");
		PadmapperPress(ControllerButton_BUTTON_A, *action);
		if (modifierFirst) {
			rt = false;
			PadmapperRelease(ControllerButton_AXIS_TRIGGERRIGHT, true);
		}
		PadmapperRelease(ControllerButton_BUTTON_A, true);
		if (!modifierFirst)
			PadmapperRelease(ControllerButton_AXIS_TRIGGERRIGHT, true);
		// Duplicate/upstream release cleanup cannot fire the ordinary action.
		PadmapperRelease(ControllerButton_BUTTON_A, true);
		EXPECT_EQ(events, (std::vector<std::string> { "quick", "quick-up" }));
		SuppressedButton = ControllerButton_NONE;
	}
}

TEST_F(MisterController, PanelCancelWinsOverGameplaySpeedbook)
{
	PadmapperOptions pad;
	bool panel = true;
	pad.AddAction("CancelAction", "", "", ControllerButton_NONE, [] {}, nullptr, [&] { return panel; });
	pad.AddAction("DisplaySpells", "", "", ControllerButton_NONE, [] {});
	LoadBindings(pad);
	auto noModifier = [](ControllerButton) { return false; };
	const auto *action = pad.findAction(ControllerButton_BUTTON_B, noModifier);
	ASSERT_NE(action, nullptr);
	EXPECT_EQ(action->key, "CancelAction");
	panel = false;
	action = pad.findAction(ControllerButton_BUTTON_B, noModifier);
	ASSERT_NE(action, nullptr);
	EXPECT_EQ(action->key, "DisplaySpells");
}

TEST_F(MisterController, TriggerAloneHasNoPanelOrMovementBlockingAction)
{
	PadmapperOptions pad;
	for (const auto key : { "Inventory", "Character", "PadHotspellMenu", "PadMenuNavigator", "MoveUp" })
		pad.AddAction(key, "", "", ControllerButton_AXIS_TRIGGERRIGHT, [] {});
	LoadBindings(pad);
	auto noModifier = [](ControllerButton) { return false; };
	EXPECT_EQ(pad.findAction(ControllerButton_AXIS_TRIGGERRIGHT, noModifier), nullptr);
	const auto *action = pad.findAction(ControllerButton_BUTTON_DPAD_RIGHT, noModifier);
	ASSERT_NE(action, nullptr);
	EXPECT_EQ(action->key, "Inventory");
}

TEST_F(MisterController, ConvenienceDefaultsAreEnabled)
{
	GameplayOptions options;
	EXPECT_TRUE(*options.quickCast);
	EXPECT_TRUE(*options.autoRefillBelt);
	EXPECT_TRUE(*options.autoGoldPickup);
}

} // namespace
} // namespace devilution
