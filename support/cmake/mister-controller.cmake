# Shared controller defaults for the native validation and MiSTer engine builds.
# Preserve the pinned upstream checkout and record the generated translation unit.
set(controller_source "${PROJECT_SOURCE_DIR}/Source/options.cpp")
file(SHA256 "${controller_source}" controller_original_sha)
if(NOT controller_original_sha STREQUAL "e7f0259173628f24a5743784a9a7e4854ab1c2e1cb827fbc8ec6754591118265")
  message(FATAL_ERROR "Unexpected pinned options.cpp for Xbox controller preset")
endif()
file(READ "${controller_source}" controller_content)
string(REPLACE "\r\n" "\n" controller_content "${controller_content}")
string(REPLACE "#define DEFAULT_PER_PIXEL_LIGHTING true"
  "#define DEFAULT_PER_PIXEL_LIGHTING false" controller_content "${controller_content}")
set(controller_content "#include \"mister_controller_bindings.hpp\"\n#include \"mister_transport_config.hpp\"\n#include <cstdlib>\n${controller_content}")
# SDL hardware cursors are not part of the framebuffer transported to FPGA.
# Keep native-window behavior unchanged; force the engine's software cursor
# for transport even when a saved INI requests a hardware cursor.
set(controller_cursor_hook "bool HardwareCursorSupported()\n{")
string(FIND "${controller_content}" "${controller_cursor_hook}" controller_cursor_site)
if(controller_cursor_site LESS 0)
  message(FATAL_ERROR "MiSTer software cursor capability hook is missing")
endif()
string(REPLACE "${controller_cursor_hook}" [[bool HardwareCursorSupported()
{
	if (::diablo::mister::transport::ParseTransportRequest(std::getenv("DIABLO_MISTER_TRANSPORT"))
	    == ::diablo::mister::transport::TransportRequest::Enabled)
		return false;]] controller_content "${controller_content}")
set(controller_registration [[actions.emplace_front(key, name, description, defaultInput, std::move(actionPressed), std::move(actionReleased), std::move(enable), index);]])
string(FIND "${controller_content}" "${controller_registration}" controller_site)
if(controller_site LESS 0)
  message(FATAL_ERROR "Xbox controller registration hook is missing")
endif()
string(REPLACE "${controller_registration}" [[if (const auto preset = mister::LookupXboxControllerBinding(key, index))
		defaultInput = *preset;
	actions.emplace_front(key, name, description, defaultInput, std::move(actionPressed), std::move(actionReleased), std::move(enable), index);]] controller_content "${controller_content}")
foreach(controller_option quickCast autoRefillBelt autoGoldPickup)
  string(REGEX MATCH ", ${controller_option}\\([^\n]+, false\\)" controller_option_line "${controller_content}")
  if(controller_option_line STREQUAL "")
    message(FATAL_ERROR "Missing Xbox gameplay default: ${controller_option}")
  endif()
  string(REGEX REPLACE ", false\\)$" ", true)" controller_option_enabled "${controller_option_line}")
  string(REPLACE "${controller_option_line}" "${controller_option_enabled}" controller_content "${controller_content}")
endforeach()
set(controller_output "${CMAKE_BINARY_DIR}/mister-controller-overlay/options.cpp")
file(CONFIGURE OUTPUT "${controller_output}" CONTENT "${controller_content}" @ONLY NEWLINE_STYLE UNIX)
file(SHA256 "${controller_output}" controller_patched_sha)
file(WRITE "${CMAKE_BINARY_DIR}/mister-controller-fixes.txt" "options.cpp ${controller_original_sha} ${controller_patched_sha}\n")
if(TARGET libdevilutionx_options)
  get_target_property(controller_sources libdevilutionx_options SOURCES)
  list(REMOVE_ITEM controller_sources options.cpp "${controller_source}")
  list(APPEND controller_sources "${controller_output}")
  set_property(TARGET libdevilutionx_options PROPERTY SOURCES "${controller_sources}")
else()
  # DevilutionX 1.5.5 keeps options.cpp in the monolithic engine library.
  get_target_property(controller_sources libdevilutionx SOURCES)
  list(REMOVE_ITEM controller_sources options.cpp "${controller_source}")
  list(APPEND controller_sources "${controller_output}")
  set_property(TARGET libdevilutionx PROPERTY SOURCES "${controller_sources}")
endif()
set_property(SOURCE "${controller_output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
  APPEND PROPERTY INCLUDE_DIRECTORIES "${CMAKE_CURRENT_LIST_DIR}/../reference")

# Keep the pinned upstream tree immutable while replacing the two actions that
# can otherwise throw a carried item directly into the world. The explicit
# checks make an upstream drift a configure-time failure rather than silently
# weakening the controller safety contract.
set(controller_diablo_source "${PROJECT_SOURCE_DIR}/Source/diablo.cpp")
file(SHA256 "${controller_diablo_source}" controller_diablo_original_sha)
if(NOT controller_diablo_original_sha STREQUAL "b7337c65281c94d2dbd1abf79248799f3c8639a9bee60bbf8a8716cbccea686e")
  message(FATAL_ERROR "Unexpected pinned diablo.cpp for Xbox controller safety")
endif()
file(READ "${controller_diablo_source}" controller_diablo_content)
string(REPLACE "\r\n" "\n" controller_diablo_content "${controller_diablo_content}")
set(controller_diablo_content "#include \"mister_controller_safety.hpp\"\n${controller_diablo_content}")

set(controller_safety_helpers [[
namespace {

mister::XboxHeldItemDropGate XboxHeldItemDrop;

bool StowXboxPanelHeldItem()
{
	Player &myPlayer = *MyPlayer;
	if (myPlayer.HoldItem.isEmpty())
		return true;

	const Item heldItem = myPlayer.HoldItem;
	bool stowed = IsStashOpen && AutoPlaceItemInStash(myPlayer, heldItem, true);
	if (!stowed)
		stowed = AutoPlaceItemInBelt(myPlayer, heldItem, true);
	if (!stowed)
		stowed = AutoPlaceItemInInventory(myPlayer, heldItem, true);
	if (!stowed) {
		myPlayer.Say(HeroSpeech::WhereWouldIPutThis);
		return false;
	}

	myPlayer.HoldItem.clear();
	NewCursor(CURSOR_HAND);
	return true;
}

void StartXboxSpellAction()
{
	LastMouseButtonAction = MouseActionType::None;
	if (XboxHeldItemDrop.Begin(invflag, !MyPlayer->HoldItem.isEmpty(), SDL_GetTicks()))
		return;

	ControllerActionHeld = GameActionType_CAST_SPELL;
	PerformSpellAction();
}

void FinishXboxSpellAction()
{
	const bool shouldDrop = XboxHeldItemDrop.Release(invflag, !MyPlayer->HoldItem.isEmpty(), SDL_GetTicks());
	ControllerActionHeld = GameActionType_NONE;
	LastMouseButtonAction = MouseActionType::None;
	if (shouldDrop)
		TryDropItem();
}

void CancelXboxPanelAction()
{
	XboxHeldItemDrop.Cancel();
	if (DoomFlag) {
		doom_close();
		return;
	}
	if (invflag && !StowXboxPanelHeldItem())
		return;

	GameAction action;
	if (spselflag)
		action = GameAction(GameActionType_TOGGLE_QUICK_SPELL_MENU);
	else if (invflag)
		action = GameAction(GameActionType_TOGGLE_INVENTORY);
	else if (sbookflag)
		action = GameAction(GameActionType_TOGGLE_SPELL_BOOK);
	else if (QuestLogIsOpen)
		action = GameAction(GameActionType_TOGGLE_QUEST_LOG);
	else if (chrflag)
		action = GameAction(GameActionType_TOGGLE_CHARACTER_INFO);
	ProcessGameAction(action);
}

} // namespace

]])
set(controller_init_marker [[void InitPadmapActions()
{]])
string(FIND "${controller_diablo_content}" "${controller_init_marker}" controller_init_site)
if(controller_init_site LESS 0)
  message(FATAL_ERROR "Xbox controller safety hook is missing")
endif()
string(REPLACE "${controller_init_marker}" "${controller_safety_helpers}${controller_init_marker}" controller_diablo_content "${controller_diablo_content}")

set(controller_spell_action [[
	    [] {
		    ControllerActionHeld = GameActionType_CAST_SPELL;
		    LastMouseButtonAction = MouseActionType::None;
		    PerformSpellAction();
	    },
	    [] {
		    ControllerActionHeld = GameActionType_NONE;
		    LastMouseButtonAction = MouseActionType::None;
	    },]])
set(controller_spell_replacement [[
	    StartXboxSpellAction,
	    FinishXboxSpellAction,]])
string(FIND "${controller_diablo_content}" "${controller_spell_action}" controller_spell_site)
if(controller_spell_site LESS 0)
  message(FATAL_ERROR "Xbox spell action hook is missing")
endif()
string(REPLACE "${controller_spell_action}" "${controller_spell_replacement}" controller_diablo_content "${controller_diablo_content}")

set(controller_cancel_action [[
	    [] {
		    if (DoomFlag) {
			    doom_close();
			    return;
		    }

		    GameAction action;
		    if (spselflag)
			    action = GameAction(GameActionType_TOGGLE_QUICK_SPELL_MENU);
		    else if (invflag)
			    action = GameAction(GameActionType_TOGGLE_INVENTORY);
		    else if (sbookflag)
			    action = GameAction(GameActionType_TOGGLE_SPELL_BOOK);
		    else if (QuestLogIsOpen)
			    action = GameAction(GameActionType_TOGGLE_QUEST_LOG);
		    else if (chrflag)
			    action = GameAction(GameActionType_TOGGLE_CHARACTER_INFO);
		    ProcessGameAction(action);
	    },]])
set(controller_cancel_replacement [[
	    CancelXboxPanelAction,]])
string(FIND "${controller_diablo_content}" "${controller_cancel_action}" controller_cancel_site)
if(controller_cancel_site LESS 0)
  message(FATAL_ERROR "Xbox cancel action hook is missing")
endif()
string(REPLACE "${controller_cancel_action}" "${controller_cancel_replacement}" controller_diablo_content "${controller_diablo_content}")

set(controller_diablo_output "${CMAKE_BINARY_DIR}/mister-controller-overlay/diablo.cpp")
file(CONFIGURE OUTPUT "${controller_diablo_output}" CONTENT "${controller_diablo_content}" @ONLY NEWLINE_STYLE UNIX)
file(SHA256 "${controller_diablo_output}" controller_diablo_patched_sha)
file(APPEND "${CMAKE_BINARY_DIR}/mister-controller-fixes.txt" "diablo.cpp ${controller_diablo_original_sha} ${controller_diablo_patched_sha}\n")
get_target_property(controller_engine_sources libdevilutionx SOURCES)
list(REMOVE_ITEM controller_engine_sources diablo.cpp "${controller_diablo_source}")
list(APPEND controller_engine_sources "${controller_diablo_output}")
set_property(TARGET libdevilutionx PROPERTY SOURCES "${controller_engine_sources}")
set_property(SOURCE "${controller_diablo_output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
  APPEND PROPERTY INCLUDE_DIRECTORIES "${CMAKE_CURRENT_LIST_DIR}/../reference")

if(TARGET mister_controller_test)
  target_include_directories(mister_controller_test PRIVATE "${CMAKE_CURRENT_LIST_DIR}/../reference")
endif()

# The old upstream hotspell circle is tied to a legacy modifier action that
# the Xbox preset deliberately unbinds. Render the same four spell icons while
# RT is held, but only when the four quick-spell bindings still match this
# preset, so a user remap is never shown a misleading overlay.
set(controller_modifier_source "${PROJECT_SOURCE_DIR}/Source/controls/modifier_hints.cpp")
file(SHA256 "${controller_modifier_source}" controller_modifier_original_sha)
if(NOT controller_modifier_original_sha STREQUAL "0feaf53285f59ea5ecbe97f96dcb88c1df908513e910796c52c9ca96e849e07c")
  message(FATAL_ERROR "Unexpected pinned modifier_hints.cpp for Xbox controller overlay")
endif()
file(READ "${controller_modifier_source}" controller_modifier_content)
string(REPLACE "\r\n" "\n" controller_modifier_content "${controller_modifier_content}")
string(REPLACE [[#include "controls/controller_motion.h"]] [[#include "controls/controller.h"
#include "controls/controller_motion.h"
#include "mister_controller_bindings.hpp"]] controller_modifier_content "${controller_modifier_content}")
set(controller_overlay_marker [[
} // namespace

void InitModifierHints()
]])
set(controller_overlay_helpers [[
void DrawXboxQuickSpellOverlay(const Surface &out)
{
	if (SimulatingMouseWithPadmapper || !IsControllerButtonPressed(ControllerButton_AXIS_TRIGGERRIGHT))
		return;

	const PadmapperOptions &padmapper = sgOptions.Padmapper;
	if (!mister::HasXboxQuickSpellLayer(
	        padmapper.ButtonComboForAction("QuickSpell1"),
	        padmapper.ButtonComboForAction("QuickSpell2"),
	        padmapper.ButtonComboForAction("QuickSpell3"),
	        padmapper.ButtonComboForAction("QuickSpell4")))
		return;

	const Rectangle &mainPanel = GetMainPanel();
	DrawSpellsCircleMenuHint(out, { mainPanel.position.x + mainPanel.size.width - (HintBoxSize * 3) - CircleMarginX - (HintBoxMargin * 2), mainPanel.position.y - CircleTop });
}

]])
string(FIND "${controller_modifier_content}" "${controller_overlay_marker}" controller_overlay_site)
if(controller_overlay_site LESS 0)
  message(FATAL_ERROR "Xbox quick-spell overlay hook is missing")
endif()
string(REPLACE "${controller_overlay_marker}" "${controller_overlay_helpers}${controller_overlay_marker}" controller_modifier_content "${controller_modifier_content}")
set(controller_hint_call [[	DrawGamepadHotspellMenu(out);]])
string(FIND "${controller_modifier_content}" "${controller_hint_call}" controller_hint_site)
if(controller_hint_site LESS 0)
  message(FATAL_ERROR "Xbox quick-spell overlay draw hook is missing")
endif()
string(REPLACE "${controller_hint_call}" "${controller_hint_call}\n\tDrawXboxQuickSpellOverlay(out);" controller_modifier_content "${controller_modifier_content}")
set(controller_modifier_output "${CMAKE_BINARY_DIR}/mister-controller-overlay/modifier_hints.cpp")
file(CONFIGURE OUTPUT "${controller_modifier_output}" CONTENT "${controller_modifier_content}" @ONLY NEWLINE_STYLE UNIX)
file(SHA256 "${controller_modifier_output}" controller_modifier_patched_sha)
file(APPEND "${CMAKE_BINARY_DIR}/mister-controller-fixes.txt" "controls/modifier_hints.cpp ${controller_modifier_original_sha} ${controller_modifier_patched_sha}\n")
get_target_property(controller_modifier_sources libdevilutionx SOURCES)
list(REMOVE_ITEM controller_modifier_sources controls/modifier_hints.cpp "${controller_modifier_source}")
list(APPEND controller_modifier_sources "${controller_modifier_output}")
set_property(TARGET libdevilutionx PROPERTY SOURCES "${controller_modifier_sources}")
set_property(SOURCE "${controller_modifier_output}" DIRECTORY "${PROJECT_SOURCE_DIR}/Source"
  APPEND PROPERTY INCLUDE_DIRECTORIES "${CMAKE_CURRENT_LIST_DIR}/../reference")
