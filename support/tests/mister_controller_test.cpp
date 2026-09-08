#include <gtest/gtest.h>

#include <array>
#include <string>
#include <string_view>
#include <vector>
#include <chrono>
#include <filesystem>

#include "controls/game_controls.h"
#include "controls/padmapper.hpp"
#include "mister_controller_bindings.hpp"
#include "mister_controller_safety.hpp"
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

TEST_F(MisterController, EveryQuickSpellKeepsItsReleaseAcrossBothReleaseOrders)
{
	struct QuickSpellCase {
		ControllerButton button;
		unsigned index;
		std::string_view quickSpell;
		std::string_view ordinaryAction;
	};
	constexpr std::array cases {
		QuickSpellCase { ControllerButton_BUTTON_X, 1, "QuickSpell1", "SpellAction" },
		QuickSpellCase { ControllerButton_BUTTON_Y, 2, "QuickSpell2", "SecondaryAction" },
		QuickSpellCase { ControllerButton_BUTTON_A, 3, "QuickSpell3", "PrimaryAction" },
		QuickSpellCase { ControllerButton_BUTTON_B, 4, "QuickSpell4", "CancelAction" },
	};

	for (const QuickSpellCase &testCase : cases) {
		for (const bool modifierFirst : { false, true }) {
			SCOPED_TRACE(testCase.quickSpell);
			SCOPED_TRACE(modifierFirst ? "release RT first" : "release face button first");
			PadmapperOptions pad;
			std::vector<std::string> events;
			pad.AddAction(testCase.ordinaryAction, "", "", ControllerButton_NONE,
			    [&] { events.emplace_back("ordinary"); }, [&] { events.emplace_back("ordinary-up"); });
			pad.AddAction("QuickSpell{}", "", "", ControllerButton_NONE,
			    [&] { events.emplace_back("quick"); }, [&] { events.emplace_back("quick-up"); }, nullptr, testCase.index);
			LoadBindings(pad);
			bool rt = true;
			auto held = [&](ControllerButton button) { return rt && button == ControllerButton_AXIS_TRIGGERRIGHT; };
			const auto *action = pad.findAction(testCase.button, held);
			ASSERT_NE(action, nullptr);
			ASSERT_EQ(action->key, testCase.quickSpell);
			PadmapperPress(testCase.button, *action);
			if (modifierFirst) {
				rt = false;
				PadmapperRelease(ControllerButton_AXIS_TRIGGERRIGHT, true);
			}
			PadmapperRelease(testCase.button, true);
			if (!modifierFirst)
				PadmapperRelease(ControllerButton_AXIS_TRIGGERRIGHT, true);
			// Duplicate/upstream release cleanup cannot fire the ordinary action.
			PadmapperRelease(testCase.button, true);
			EXPECT_EQ(events, (std::vector<std::string> { "quick", "quick-up" }));
			SuppressedButton = ControllerButton_NONE;
		}
	}
}

TEST_F(MisterController, ControllerContractBindingsAreExact)
{
	struct ExpectedBinding {
		std::string_view action;
		ControllerButton modifier;
		ControllerButton button;
	};
	constexpr std::array expected {
		ExpectedBinding { "QuickSpell1", ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_X },
		ExpectedBinding { "QuickSpell2", ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_Y },
		ExpectedBinding { "QuickSpell3", ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_A },
		ExpectedBinding { "QuickSpell4", ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_B },
		ExpectedBinding { "PrimaryAction", ControllerButton_NONE, ControllerButton_BUTTON_A },
		ExpectedBinding { "SecondaryAction", ControllerButton_NONE, ControllerButton_BUTTON_Y },
		ExpectedBinding { "SpellAction", ControllerButton_NONE, ControllerButton_BUTTON_X },
		ExpectedBinding { "CancelAction", ControllerButton_NONE, ControllerButton_BUTTON_B },
		ExpectedBinding { "DisplaySpells", ControllerButton_NONE, ControllerButton_BUTTON_B },
		ExpectedBinding { "UseHealthPotion", ControllerButton_NONE, ControllerButton_BUTTON_LEFTSHOULDER },
		ExpectedBinding { "UseManaPotion", ControllerButton_NONE, ControllerButton_BUTTON_RIGHTSHOULDER },
		ExpectedBinding { "StandGround", ControllerButton_NONE, ControllerButton_AXIS_TRIGGERLEFT },
		ExpectedBinding { "ToggleItemHighlighting", ControllerButton_NONE, ControllerButton_BUTTON_LEFTSTICK },
		ExpectedBinding { "SpellBook", ControllerButton_NONE, ControllerButton_BUTTON_DPAD_UP },
		ExpectedBinding { "Inventory", ControllerButton_NONE, ControllerButton_BUTTON_DPAD_RIGHT },
		ExpectedBinding { "QuestLog", ControllerButton_NONE, ControllerButton_BUTTON_DPAD_DOWN },
		ExpectedBinding { "Character", ControllerButton_NONE, ControllerButton_BUTTON_DPAD_LEFT },
		ExpectedBinding { "ToggleAutomap", ControllerButton_NONE, ControllerButton_BUTTON_BACK },
		ExpectedBinding { "ToggleGameMenu1", ControllerButton_NONE, ControllerButton_BUTTON_START },
		ExpectedBinding { "LeftMouseClick1", ControllerButton_NONE, ControllerButton_BUTTON_RIGHTSTICK },
		ExpectedBinding { "RightMouseClick1", ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_RIGHTSTICK },
		ExpectedBinding { "AutomapMoveUp", ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_DPAD_UP },
		ExpectedBinding { "AutomapMoveDown", ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_DPAD_DOWN },
		ExpectedBinding { "AutomapMoveLeft", ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_DPAD_LEFT },
		ExpectedBinding { "AutomapMoveRight", ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_DPAD_RIGHT },
		ExpectedBinding { "MoveUp", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "MoveDown", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "MoveLeft", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "MoveRight", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "MouseUp", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "MouseDown", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "MouseLeft", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "MouseRight", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "LeftMouseClick2", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "RightMouseClick2", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "PadHotspellMenu", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "PadMenuNavigator", ControllerButton_NONE, ControllerButton_NONE },
		ExpectedBinding { "ToggleGameMenu2", ControllerButton_NONE, ControllerButton_NONE },
	};

	for (const ExpectedBinding &binding : expected) {
		SCOPED_TRACE(binding.action);
		const auto actual = mister::LookupXboxControllerBinding(binding.action);
		ASSERT_TRUE(actual.has_value());
		EXPECT_EQ(actual->modifier, binding.modifier);
		EXPECT_EQ(actual->button, binding.button);
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

TEST(MisterControllerSafety, HeldItemDropNeedsAContinuousHalfSecondHold)
{
	mister::XboxHeldItemDropGate gate;
	EXPECT_TRUE(gate.Begin(true, true, 1000));
	EXPECT_FALSE(gate.Release(true, true, 1499));

	EXPECT_TRUE(gate.Begin(true, true, 1000));
	EXPECT_TRUE(gate.Release(true, true, 1500));

	EXPECT_TRUE(gate.Begin(true, true, UINT32_MAX - 200));
	EXPECT_TRUE(gate.Release(true, true, 299));
}

TEST(MisterControllerSafety, HeldItemDropIsCancelledByAClosedPanelOrExplicitCancel)
{
	mister::XboxHeldItemDropGate gate;
	EXPECT_TRUE(gate.Begin(true, true, 1000));
	EXPECT_FALSE(gate.Release(false, true, 2000));

	EXPECT_TRUE(gate.Begin(true, true, 3000));
	gate.Cancel();
	EXPECT_FALSE(gate.Release(true, true, 4000));
}

TEST_F(MisterController, QuickSpellOverlayRequiresTheExactXboxLayer)
{
	const auto spell1 = mister::LookupXboxControllerBinding("QuickSpell1");
	const auto spell2 = mister::LookupXboxControllerBinding("QuickSpell2");
	const auto spell3 = mister::LookupXboxControllerBinding("QuickSpell3");
	const auto spell4 = mister::LookupXboxControllerBinding("QuickSpell4");
	ASSERT_TRUE(spell1.has_value());
	ASSERT_TRUE(spell2.has_value());
	ASSERT_TRUE(spell3.has_value());
	ASSERT_TRUE(spell4.has_value());
	EXPECT_TRUE(mister::HasXboxQuickSpellLayer(*spell1, *spell2, *spell3, *spell4));
	EXPECT_FALSE(mister::HasXboxQuickSpellLayer(
	    *spell1, *spell2, *spell3, ControllerButtonCombo { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_Y }));
}

} // namespace
} // namespace devilution
