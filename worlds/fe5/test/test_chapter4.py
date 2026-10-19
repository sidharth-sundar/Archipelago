"""Generation contracts. Native menu/escape acceptance is tested separately."""
from collections import Counter
from itertools import product
import unittest

from BaseClasses import CollectionState
from ..definitions import ITEMS, LOCATIONS, PROTOCOL, COMPANION_SIZE, CHAPTERS
from ..capacity import capacity_report
from ..options import DebugStartChapter
from ..patchcore import valid_mask
from .test_world import generate


class ChapterFourGenerationTests(unittest.TestCase):
    def test_all_categories_and_stable_ids(self):
        mw = generate(options={1: dict(shopsanity=1, capturesanity_easy=1, capturesanity_hard=1)})
        locations = [l for l in mw.get_locations() if l.address is not None]
        pool = Counter(l.item.name for l in locations)
        self.assertEqual((len(locations), pool['Nothing']), (63, 42))
        self.assertEqual(pool['Vulnerary'], 6)
        self.assertEqual([l['bit'] for l in LOCATIONS], list(range(63)))
        self.assertEqual([l['id'] for l in LOCATIONS], list(range(16666880, 16666943)))
        self.assertEqual([i['id'] for i in ITEMS], list(range(16666624, 16666660)))
        self.assertEqual((PROTOCOL, COMPANION_SIZE), (11, 0xc00))
        self.assertEqual(mw.worlds[1].enabled_mask, (1 << 63)-1)
        self.assertTrue(valid_mask(mw.worlds[1].enabled_mask))
        self.assertFalse(valid_mask(1 << 63))
        self.assertEqual(CHAPTERS[-1]['blue_escape_quota'], 5)
        self.assertEqual(mw.worlds[1].physical_capacity_report['total'], 21)

    def test_independent_escape_and_chest_categories(self):
        for blue, green, chests, recruit, talk in product((0, 1), repeat=5):
            with self.subTest(blue=blue, green=green, chests=chests, recruit=recruit, talk=talk):
                mw = generate(options={1: dict(blue_escapesanity=blue, green_escapesanity=green,
                    chestsanity=chests, recruitment_checks=recruit, conversation_checks=talk)})
                locations = [l for l in mw.get_region('Chapter 4', 1).locations if l.address]
                self.assertEqual(len(locations), 5*blue + 6*green + 4*chests + 6*recruit + talk + 1)
                pool = Counter(l.item.name for l in mw.get_locations() if l.address)
                for name in ('Rapier', 'Javelin', 'Steel Sword'):
                    self.assertEqual(pool[name], chests)
                self.assertEqual(sum(pool.values()), len(mw.worlds[1].enabled_locations))
                self.assertTrue(valid_mask(mw.worlds[1].enabled_mask))

    def test_debug_start_and_reward_independent_victory(self):
        self.assertEqual(DebugStartChapter.from_any(4).value, 5)
        for start in (1, 2, '2x', 3, 4):
            mw = generate(options={1: dict(debug_start_chapter=start)})
            state = CollectionState(mw)
            self.assertEqual(mw.get_region('Chapter 4', 1).can_reach(state), start == 4)
            self.assertFalse(mw.completion_condition[1](state))
            state.sweep_for_advancements()
            self.assertTrue(mw.completion_condition[1](state))
            self.assertFalse(any(state.has(i['name'], 1) for i in ITEMS))
            self.assertEqual(mw.get_location('Chapter 3 - Seize', 1).item.name, 'Chapter 3 Cleared')

    def test_mixed_players_and_determinism(self):
        options = {1: dict(blue_escapesanity=0, green_escapesanity=1),
                   2: dict(blue_escapesanity=1, green_escapesanity=0, chestsanity=0)}
        def placements():
            mw = generate(2, seed=2026101804, options=options)
            self.assertTrue(mw.can_beat_game())
            return [(l.player, l.address, l.item.name, l.item.player) for l in mw.get_locations() if l.address]
        first = placements()
        self.assertEqual(first, placements())
        self.assertTrue(any(player != recipient for player, _, _, recipient in first))

    def test_capacity_report_is_advisory(self):
        self.assertFalse(capacity_report(21, 132, 0)['audit_recommended'])
        self.assertTrue(capacity_report(21, 132, 1)['audit_recommended'])
        self.assertEqual(capacity_report(600, 0, 0)['total'], 600)
        with self.assertRaises(ValueError):
            capacity_report(1, -1, 0)

    def test_validation_physical_pool(self):
        mw = generate(options={1: dict(shopsanity=1, capturesanity_easy=1, capturesanity_hard=1,
            enable_extra_valuable_items=1, extra_arms_scrolls=1, extra_critical_manuals=1)})
        pool = Counter(l.item.name for l in mw.get_locations() if l.address)
        self.assertEqual((sum(pool.values()), pool['Nothing']), (63, 40))
        self.assertEqual(pool['Arms Scroll'], 1)
        self.assertEqual(pool['Critical Manual'], 1)
