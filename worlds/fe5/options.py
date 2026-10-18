from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from Options import Choice, DefaultOnToggle, Toggle, Range, PerGameCommonOptions, OptionGroup


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


class EnableExtraValuableItems(Toggle):
    """Add the configured guaranteed rewards; generation fails if they do not fit."""
    display_name = "Enable Extra Valuable Items"


class BoosterCount(Range):
    """Guaranteed additional copies, ignored when random booster mode is enabled."""
    range_start = 0
    range_end = 9
    default = 0


class StaffCount(Range):
    """Guaranteed additional full-durability staves; normal rank restrictions apply."""
    range_start = 0
    range_end = 3
    default = 0


class RandomStatBoosters(Toggle):
    """Ignore individual booster counts and draw the configured number with replacement."""
    display_name = "Random Stat Boosters"


class RandomStatBoosterCount(BoosterCount):
    """Number of equally weighted, seeded draws when Random Stat Boosters is on."""
    display_name = "Random Stat Booster Count"


class ExcludeBootsFromRandomStatBoosters(Toggle):
    """Exclude Boots (native Leg Ring) from random draws; manual Boots are unaffected."""
    display_name = "Exclude Boots from Random Stat Boosters"


class ExtraLifeRings(BoosterCount):
    display_name = "Extra Life Rings"


class ExtraSpeedRings(BoosterCount):
    display_name = "Extra Speed Rings"


class ExtraMagicRings(BoosterCount):
    display_name = "Extra Magic Rings"


class ExtraStrengthRings(BoosterCount):
    display_name = "Extra Strength Rings"


class ExtraLuckRings(BoosterCount):
    display_name = "Extra Luck Rings"


class ExtraSkillRings(BoosterCount):
    display_name = "Extra Skill Rings"


class ExtraShieldRings(BoosterCount):
    display_name = "Extra Shield Rings"


class ExtraBodyRings(BoosterCount):
    display_name = "Extra Body Rings"


class ExtraBoots(BoosterCount):
    display_name = "Extra Boots"


class ExtraWarpStaves(StaffCount):
    display_name = "Extra Warp Staves"


class ExtraRescueStaves(StaffCount):
    display_name = "Extra Rescue Staves"


class ExtraArmsScrolls(BoosterCount):
    """Guaranteed Arms Scrolls: +50 WEXP, equipped weapon first, otherwise staff; cap A."""
    display_name = "Extra Arms Scrolls"


class ExtraCriticalManuals(BoosterCount):
    """Guaranteed Critical Manuals: +1 persistent FCM, up to five."""
    display_name = "Extra Critical Manuals"


class FillerEffectChance(Range):
    """Chance of replacing each remaining Nothing with a weighted effect."""
    display_name = "Filler Effect Chance"
    range_start = 0
    range_end = 100
    default = 0


class EffectWeight(Range):
    """Relative effect-selection weight; zero disables this effect."""
    range_start = 0
    range_end = 100
    default = 1


class BossMusicWeight(EffectWeight):
    display_name = "Boss Music Weight"


class HealPlayersWeight(EffectWeight):
    display_name = "Heal Players Weight"


class HealEnemiesWeight(EffectWeight):
    display_name = "Heal Enemies Weight"


class FogWeight(EffectWeight):
    display_name = "Fog Weight"


class MovementOneWeight(EffectWeight):
    display_name = "Movement One Weight"


class DancerReinforcementsWeight(EffectWeight):
    display_name = "Dancer Reinforcements Weight"


class BallistaReinforcementsWeight(EffectWeight):
    display_name = "Ballista Reinforcements Weight"


class SiegeReinforcementsWeight(EffectWeight):
    display_name = "Siege Reinforcements Weight"


class RotatePlayersWeight(EffectWeight):
    display_name = "Rotate Players Weight"


class RotateEnemiesWeight(EffectWeight):
    display_name = "Rotate Enemies Weight"


class DebugStartChapter(Range):
    """Developer start; Chapter 2 releases enabled Chapter 1 checks normally."""
    display_name = "Debug Start Chapter"
    range_start = 1
    range_end = 2
    default = 1


class DebugExperience(Range):
    """EXP per skipped chapter; 70 EXP alone normally grants no full level."""
    display_name = "Debug EXP Per Chapter"
    range_start = 0
    range_end = 1000
    default = 70


class DebugGrowthMode(Choice):
    """Only bootstrap level gains; normal gameplay growths are unchanged."""
    display_name = "Debug Growth Mode"
    option_fixed = 0
    option_seeded_random = 1
    default = 0

    @classmethod
    def from_text(cls, text):
        # AP reserves the literal "random" for random option selection. Here
        # it explicitly selects randomized bootstrap growths instead.
        if text.lower() == "random":
            return cls(1)
        return super().from_text(text)


extra_option_groups = [
    OptionGroup("Developer debugging", [DebugStartChapter, DebugExperience, DebugGrowthMode]),
    OptionGroup("Traps and effects", [FillerEffectChance, BossMusicWeight, HealPlayersWeight,
                                      HealEnemiesWeight, FogWeight, MovementOneWeight,
                                      DancerReinforcementsWeight, BallistaReinforcementsWeight, SiegeReinforcementsWeight, RotatePlayersWeight, RotateEnemiesWeight]),
    OptionGroup("Extra Valuable Items", [EnableExtraValuableItems]),
    OptionGroup("Stat Boosters", [RandomStatBoosters, RandomStatBoosterCount, ExcludeBootsFromRandomStatBoosters,
        ExtraLifeRings, ExtraSpeedRings, ExtraMagicRings, ExtraStrengthRings, ExtraLuckRings, ExtraSkillRings, ExtraShieldRings, ExtraBodyRings, ExtraBoots]),
    OptionGroup("Staves", [ExtraWarpStaves, ExtraRescueStaves]),
    OptionGroup("Custom Items", [ExtraArmsScrolls, ExtraCriticalManuals]),
]


@dataclass
class FE5Options(PerGameCommonOptions):
    debug_start_chapter: DebugStartChapter
    debug_exp_per_chapter: DebugExperience
    debug_growth_mode: DebugGrowthMode
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
    enable_extra_valuable_items: EnableExtraValuableItems
    random_stat_boosters: RandomStatBoosters
    random_stat_booster_count: RandomStatBoosterCount
    exclude_boots_from_random_stat_boosters: ExcludeBootsFromRandomStatBoosters
    extra_life_rings: ExtraLifeRings
    extra_speed_rings: ExtraSpeedRings
    extra_magic_rings: ExtraMagicRings
    extra_strength_rings: ExtraStrengthRings
    extra_luck_rings: ExtraLuckRings
    extra_skill_rings: ExtraSkillRings
    extra_shield_rings: ExtraShieldRings
    extra_body_rings: ExtraBodyRings
    extra_boots: ExtraBoots
    extra_warp_staves: ExtraWarpStaves
    extra_rescue_staves: ExtraRescueStaves
    extra_arms_scrolls: ExtraArmsScrolls
    extra_critical_manuals: ExtraCriticalManuals
    filler_effect_chance: FillerEffectChance
    boss_music_weight: BossMusicWeight
    heal_players_weight: HealPlayersWeight
    heal_enemies_weight: HealEnemiesWeight
    fog_weight: FogWeight
    movement_one_weight: MovementOneWeight
    dancer_reinforcements_weight: DancerReinforcementsWeight
    ballista_reinforcements_weight: BallistaReinforcementsWeight
    siege_reinforcements_weight: SiegeReinforcementsWeight
    rotate_players_weight: RotatePlayersWeight
    rotate_enemies_weight: RotateEnemiesWeight
