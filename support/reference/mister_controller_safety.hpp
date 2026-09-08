#pragma once

#include <cstdint>

namespace devilution::mister {

// A carried item may be dropped from the inventory only after this much
// continuous X hold time. Short presses retain the item for normal panel use.
inline constexpr uint32_t XboxHeldItemDropHoldMilliseconds = 500;

class XboxHeldItemDropGate {
public:
	// Returns true when the X press is reserved for a possible held-item drop.
	[[nodiscard]] bool Begin(bool inventoryOpen, bool holdingItem, uint32_t now)
	{
		armed_ = inventoryOpen && holdingItem;
		if (armed_)
			startedAt_ = now;
		return armed_;
	}

	// Returns true only for a completed deliberate hold. Unsigned subtraction
	// preserves the intended duration across SDL's 32-bit tick wraparound.
	[[nodiscard]] bool Release(bool inventoryOpen, bool holdingItem, uint32_t now)
	{
		const bool shouldDrop = armed_ && inventoryOpen && holdingItem
		    && static_cast<uint32_t>(now - startedAt_) >= XboxHeldItemDropHoldMilliseconds;
		Cancel();
		return shouldDrop;
	}

	void Cancel() { armed_ = false; }

	[[nodiscard]] bool armed() const { return armed_; }

private:
	uint32_t startedAt_ = 0;
	bool armed_ = false;
};

} // namespace devilution::mister
