import copy
import json
import os
from pathlib import Path
import unittest
from BaseClasses import CollectionState
from ..debug import DEFAULTS, ROSTER, debug_config_bytes, debug_units
from ..definitions import LOCATIONS, ITEMS
from ..options import DebugStartChapter, DebugExperience, DebugGrowthMode
from ..patchcore import apply_patch, valid_mask
from ..rom import make_seed_data
from .test_world import generate


class ChapterTwoTests(unittest.TestCase):
    def test_independent_ronan_checks_and_no_character_reward(self):
        for village in (0, 1):
            for recruitment in (0, 1):
                mw = generate(options={1: dict(village_checks=village, recruitment_checks=recruitment, shopsanity=1)})
                names = {l.name for l in mw.get_locations() if l.address}
                self.assertEqual('Chapter 2 - Ronan House' in names, bool(village))
                self.assertEqual('Chapter 2 - Recruit Ronan' in names, bool(recruitment))
                self.assertFalse(any('Ronan' in l.item.name for l in mw.get_locations()))
                self.assertTrue(valid_mask(mw.worlds[1].enabled_mask))
        self.assertEqual([l['id'] for l in LOCATIONS], list(range(16666880, 16666920)))
        self.assertFalse(any('Ronan' in i['name'] for i in ITEMS))

    def test_clearance_and_debug_reachability(self):
        for start in (1, 2):
            mw = generate(options={1: dict(debug_start_chapter=start)})
            empty = CollectionState(mw)
            self.assertEqual(mw.get_region('Chapter 2', 1).can_reach(empty), start == 2)
            self.assertFalse(mw.completion_condition[1](empty))
            empty.sweep_for_advancements()
            self.assertTrue(empty.has('Chapter 1 Cleared', 1))
            self.assertTrue(mw.completion_condition[1](empty))
            self.assertEqual(len([l for l in mw.get_locations() if l.address]), 34)

    def test_debug_options_and_identity(self):
        self.assertEqual(DebugGrowthMode.from_any('random').value, 1)
        self.assertEqual(DebugGrowthMode.from_any('fixed').value, 0)
        for cls, values in ((DebugStartChapter, (0, 4)), (DebugExperience, (-1, 1001))):
            for value in values:
                with self.assertRaises(Exception): cls.from_any(value)
        for key, value in [('debug_start_chapter', 2), ('debug_exp_per_chapter', 100), ('debug_growth_mode', 'random')]:
            normal, changed = generate().worlds[1], generate(options={1: {key: value}}).worlds[1]
            self.assertNotEqual(normal.identity, changed.identity)
            self.assertEqual(json.loads(make_seed_data(changed))['debug_config'], changed.fill_slot_data()['debug_config'])
        with self.assertRaises(ValueError): debug_config_bytes(DEFAULTS | {'debug_start_chapter': True})


@unittest.skipUnless(os.getenv('FE5_BASE_ROM'), 'Private LM binary required')
class DebugNativeDataTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(os.environ['FE5_BASE_ROM']).read_bytes()

    def test_growths_exp_caps_and_rng_determinism(self):
        config = DEFAULTS | {'debug_start_chapter': 2}
        data = debug_units(self.base, config, bytes(16))
        self.assertEqual(len(data), 132)
        for index, (character, level) in enumerate(ROSTER):
            self.assertEqual(list(data[index*12:index*12+3]), [character, level, 70])
        fixed = debug_units(self.base, config | {'debug_exp_per_chapter': 1000}, bytes(16))
        self.assertEqual(fixed[:4], bytes([1, 11, 0, 29]))  # Leif: 22 HP + 70% * 10
        self.assertEqual(fixed[2*12+1:2*12+3], bytes([20, 0]))  # Eyvel caps without promotion
        random_config = config | {'debug_exp_per_chapter': 1000, 'debug_growth_mode': 1}
        a = debug_units(self.base, random_config, bytes(16))
        self.assertEqual(a, debug_units(self.base, random_config, bytes(16)))
        self.assertNotEqual(a, debug_units(self.base, random_config, bytes([1])*16))
        for n, (character, _) in enumerate(ROSTER):
            c = self.base[0x31a2d+(character-1)*48+44]
            o = 0x30000+(c-1)*36
            class_stats = list(self.base[o:o+7])+[0,self.base[o+7]]
            for i, stat in enumerate(a[n*12+3:n*12+12]):
                self.assertLessEqual(stat if i == 0 else stat+class_stats[i], 80 if i == 0 else 20)

    def test_seed_specific_bootstrap_and_native_chapter1_ending(self):
        runtime = json.loads(Path(__file__).parents[1].joinpath('data/runtime.json').read_text())
        for chapter in (1, 2):
            seed = json.loads(make_seed_data(generate(options={1: dict(debug_start_chapter=chapter)}).worlds[1]))
            rom = apply_patch(self.base, runtime, seed)
            self.assertEqual(rom[0x4a004a:0x4a0050], debug_config_bytes(seed['debug_config']))
            self.assertEqual(rom[0x3e8001:0x3e8004] == self.base[0x3e8001:0x3e8004], chapter == 1)
            self.assertEqual(rom[0x3e8543:0x3e85c5], self.base[0x3e8543:0x3e85c5])
        old = copy.deepcopy(seed); old['protocol'] = 7
        with self.assertRaises(ValueError): apply_patch(self.base, runtime, old)
        old = copy.deepcopy(seed); old['chapter'] = 1
        with self.assertRaises(ValueError): apply_patch(self.base, runtime, old)
        invalid = copy.deepcopy(runtime)
        invalid['symbols']['ap_debug_units'] = invalid['symbols']['ap_end']
        with self.assertRaises(ValueError): apply_patch(self.base, invalid, seed)
