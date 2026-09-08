#pragma once

#include <array>
#include <optional>
#include <string_view>

#include "controls/controller_buttons.h"

namespace devilution::mister {

/**
 * A present lookup result replaces the upstream Padmapper default.  A present
 * all-NONE combo intentionally unbinds that action; std::nullopt leaves the
 * upstream default untouched.
 *
 * Call LookupXboxControllerBinding(key, index) before PadmapperOptions adds an
 * action. Dynamic quick-spell registration uses key "QuickSpell{}" and a
 * one-based index, while callers holding an expanded "QuickSpell1" key are
 * supported as well.
 */
struct XboxControllerBinding {
	std::string_view actionKey;
	unsigned dynamicIndex;
	ControllerButtonCombo combo;
};

inline constexpr ControllerButtonCombo UnboundControllerButtonCombo {};

inline constexpr std::array XboxControllerBindings {
	// Four native quick-spell slots. RT itself remains unbound.
	XboxControllerBinding { "QuickSpell{}", 1, { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_X } },
	XboxControllerBinding { "QuickSpell{}", 2, { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_Y } },
	XboxControllerBinding { "QuickSpell{}", 3, { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_A } },
	XboxControllerBinding { "QuickSpell{}", 4, { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_B } },

	// Gameplay actions.
	XboxControllerBinding { "PrimaryAction", 0, ControllerButton_BUTTON_A },
	XboxControllerBinding { "SecondaryAction", 0, ControllerButton_BUTTON_Y },
	XboxControllerBinding { "SpellAction", 0, ControllerButton_BUTTON_X },
	XboxControllerBinding { "CancelAction", 0, ControllerButton_BUTTON_B },
	XboxControllerBinding { "DisplaySpells", 0, ControllerButton_BUTTON_B },
	XboxControllerBinding { "UseHealthPotion", 0, ControllerButton_BUTTON_LEFTSHOULDER },
	XboxControllerBinding { "UseManaPotion", 0, ControllerButton_BUTTON_RIGHTSHOULDER },
	XboxControllerBinding { "StandGround", 0, ControllerButton_AXIS_TRIGGERLEFT },
	XboxControllerBinding { "ToggleItemHighlighting", 0, ControllerButton_BUTTON_LEFTSTICK },

	// Panel shortcuts and ordinary game menu. Panel enable predicates retain
	// their upstream context priority over the gameplay B action.
	XboxControllerBinding { "SpellBook", 0, ControllerButton_BUTTON_DPAD_UP },
	XboxControllerBinding { "Inventory", 0, ControllerButton_BUTTON_DPAD_RIGHT },
	XboxControllerBinding { "QuestLog", 0, ControllerButton_BUTTON_DPAD_DOWN },
	XboxControllerBinding { "Character", 0, ControllerButton_BUTTON_DPAD_LEFT },
	XboxControllerBinding { "ToggleAutomap", 0, ControllerButton_BUTTON_BACK },
	XboxControllerBinding { "ToggleGameMenu1", 0, ControllerButton_BUTTON_START },

	// Precision mouse actions and automap panning.
	XboxControllerBinding { "LeftMouseClick1", 0, ControllerButton_BUTTON_RIGHTSTICK },
	XboxControllerBinding { "RightMouseClick1", 0, { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_RIGHTSTICK } },
	XboxControllerBinding { "AutomapMoveUp", 0, { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_DPAD_UP } },
	XboxControllerBinding { "AutomapMoveDown", 0, { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_DPAD_DOWN } },
	XboxControllerBinding { "AutomapMoveLeft", 0, { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_DPAD_LEFT } },
	XboxControllerBinding { "AutomapMoveRight", 0, { ControllerButton_AXIS_TRIGGERRIGHT, ControllerButton_BUTTON_DPAD_RIGHT } },

	// Remove defaults that conflict with the Xbox preset. Unknown actions remain
	// nullopt and therefore retain the named upstream default.
	XboxControllerBinding { "MoveUp", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "MoveDown", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "MoveLeft", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "MoveRight", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "MouseUp", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "MouseDown", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "MouseLeft", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "MouseRight", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "LeftMouseClick2", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "RightMouseClick2", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "PadHotspellMenu", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "PadMenuNavigator", 0, UnboundControllerButtonCombo },
	XboxControllerBinding { "ToggleGameMenu2", 0, UnboundControllerButtonCombo },
};

[[nodiscard]] constexpr std::optional<unsigned> QuickSpellIndex(std::string_view actionKey)
{
	constexpr std::string_view Prefix = "QuickSpell";
	if (!actionKey.starts_with(Prefix) || actionKey.size() == Prefix.size())
		return std::nullopt;

	unsigned index = 0;
	for (const char character : actionKey.substr(Prefix.size())) {
		if (character < '0' || character > '9')
			return std::nullopt;
		index = index * 10 + static_cast<unsigned>(character - '0');
	}
	return index;
}

[[nodiscard]] constexpr std::optional<ControllerButtonCombo> LookupXboxControllerBinding(std::string_view actionKey, unsigned dynamicIndex = 0)
{
	if (actionKey != "QuickSpell{}") {
		if (const std::optional<unsigned> quickSpellIndex = QuickSpellIndex(actionKey); quickSpellIndex.has_value()) {
			actionKey = "QuickSpell{}";
			dynamicIndex = *quickSpellIndex;
		}
	}

	for (const XboxControllerBinding &binding : XboxControllerBindings) {
		if (binding.actionKey == actionKey && binding.dynamicIndex == dynamicIndex)
			return binding.combo;
	}
	return std::nullopt;
}

[[nodiscard]] constexpr bool HasXboxQuickSpellLayer(
    const ControllerButtonCombo &quickSpell1,
    const ControllerButtonCombo &quickSpell2,
    const ControllerButtonCombo &quickSpell3,
    const ControllerButtonCombo &quickSpell4)
{
	return quickSpell1.modifier == ControllerButton_AXIS_TRIGGERRIGHT && quickSpell1.button == ControllerButton_BUTTON_X
	    && quickSpell2.modifier == ControllerButton_AXIS_TRIGGERRIGHT && quickSpell2.button == ControllerButton_BUTTON_Y
	    && quickSpell3.modifier == ControllerButton_AXIS_TRIGGERRIGHT && quickSpell3.button == ControllerButton_BUTTON_A
	    && quickSpell4.modifier == ControllerButton_AXIS_TRIGGERRIGHT && quickSpell4.button == ControllerButton_BUTTON_B;
}

} // namespace devilution::mister
