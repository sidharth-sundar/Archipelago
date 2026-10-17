from dataclasses import dataclass
from Options import DefaultOnToggle, PerGameCommonOptions


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


@dataclass
class FE5Options(PerGameCommonOptions):
    recruitment_checks: RecruitmentChecks
    village_checks: VillageChecks
    conversation_checks: ConversationChecks
    chapter_completion_checks: ChapterCompletionChecks
