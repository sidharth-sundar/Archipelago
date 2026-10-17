from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from Options import DefaultOnToggle, Toggle, Range, PerGameCommonOptions


class RecruitmentChecks(DefaultOnToggle):
    """Check each Chapter 1 starting/arriving character when they join."""
    display_name = "Recruitment Checks"


class VillageChecks(DefaultOnToggle):
    """Randomize the five village rewards. Off restores their vanilla items."""
    display_name = "Village Checks"


class ConversationChecks(DefaultOnToggle):
    """Check Eyvel–Dagdar and Osian–Tanya Talk events."""
    display_name = "Conversation Checks"


class ChapterCompletionChecks(DefaultOnToggle):
    """Add a randomized seizure location; victory always requires seizure."""
    display_name = "Chapter Completion Checks"


class ArmorySanity(Toggle):
    """Replace each supported armory stock slot's first purchase with a check.
    Chapter 1 has no armory; this option is reserved for supported armories.
    """
    display_name = "Armorysanity"


class ShopSanity(Toggle):
    """Replace each vendor stock slot's first purchase with a check, then restore vanilla stock."""
    display_name = "Shopsanity"


class StockItemsInPool(DefaultOnToggle):
    """Add each original stock item to the pool when matching sanity is enabled."""
    display_name = "Stock Items in Pool"


class PriceMultiplier(Range):
    """Purchase multiplier: 0.1 to 10.0 in 0.1 steps. Bargain applies afterwards.
    Applies even without sanity. Sale prices are unchanged.
    Internally represented in tenths; YAML numbers are ordinary multipliers.
    """
    display_name = "Purchase Price Multiplier"
    range_start = 1
    range_end = 100
    default = "1.0"

    @classmethod
    def from_any(cls, value):
        if isinstance(value, cls):
            return value
        try:
            number = Decimal(str(value)) * 10
            if not number.is_finite() or number != number.to_integral_value():
                raise ValueError
            return cls(int(number))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Price multiplier must be 0.1 through 10.0 in 0.1 steps") from exc

    @classmethod
    def from_text(cls, text):
        return cls.from_any(text)

    @classmethod
    def get_option_name(cls, value):
        return f"{value / 10:.1f}"


@dataclass
class FE5Options(PerGameCommonOptions):
    recruitment_checks: RecruitmentChecks
    village_checks: VillageChecks
    conversation_checks: ConversationChecks
    chapter_completion_checks: ChapterCompletionChecks
    armorysanity: ArmorySanity
    armory_items_in_pool: StockItemsInPool
    armory_price_multiplier: PriceMultiplier
    shopsanity: ShopSanity
    shop_items_in_pool: StockItemsInPool
    shop_price_multiplier: PriceMultiplier
