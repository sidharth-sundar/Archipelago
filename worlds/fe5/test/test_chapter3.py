"""Chapter 3 generation and exact-base patch contracts; emulator evidence is separate."""
from collections import Counter
import json
import os
from pathlib import Path
import unittest

from BaseClasses import CollectionState
from ..definitions import ITEMS, LOCATIONS, LOCATION_MASK_BYTES, PROTOCOL
from ..debug import debug_units
from ..options import DebugStartChapter
from ..patchcore import apply_patch, valid_mask
from ..protocol import QueueModel, ProtocolError, encode_receipt, checks_for
from ..rom import make_seed_data
from .test_world import generate


class ChapterThreeTests(unittest.TestCase):
    def test_full_pool_and_new_locations(self):
        mw = generate(options={1: dict(shopsanity=1, capturesanity_easy=1, capturesanity_hard=1)})
        locations = [l for l in mw.get_locations() if l.address]
        pool = Counter(l.item.name for l in locations)
        self.assertEqual((len(locations), pool['Nothing']), (63, 42))
        self.assertEqual(pool['Vulnerary'], 6)
        for item in ("Baldr's Scroll", 'Armorslayer', 'Meteor', 'Door Key', 'Shield Ring'):
            self.assertEqual(pool[item], 1)
        self.assertEqual([l['bit'] for l in LOCATIONS if l['chapter'] == 3], list(range(31, 40)))
        self.assertEqual((PROTOCOL, LOCATION_MASK_BYTES), (11, 8))
        self.assertEqual(mw.worlds[1].enabled_mask, (1 << 63)-1)

    def test_chests_independent_and_no_location_tokens_in_receipts(self):
        for enabled in (0, 1):
            mw = generate(options={1: dict(chestsanity=enabled, village_checks=0)})
            pool = Counter(l.item.name for l in mw.get_locations() if l.address)
            self.assertEqual((pool['Armorslayer'], pool['Meteor']), (enabled, enabled))
            self.assertEqual(pool["Baldr's Scroll"], 0)
            self.assertTrue(valid_mask(mw.worlds[1].enabled_mask))
        for native in (0xaa, 0xab, 0xac, 0xad):
            self.assertNotIn(native, [i['native'] for i in ITEMS])
            with self.assertRaises(ProtocolError):
                encode_receipt(0, native)

    def test_high_locations_cleanup_and_partial_masks(self):
        mask = (1 << 40)-1
        self.assertEqual(checks_for(1 << 39, False, mask), [16666919])
        self.assertEqual(len(checks_for(0, True, mask)), 40)
        for bit in (31, 32, 34, 35, 37, 39, 63):
            self.assertFalse(valid_mask(1 << bit))
        self.assertFalse(valid_mask(mask | 1 << 40))

    def test_goal_and_debug_start(self):
        self.assertEqual([DebugStartChapter.from_any(v).value for v in (1, 2, '2x', 3)], [1, 2, 3, 4])
        for chapter in (1, 2, '2x', 3):
            mw = generate(options={1: dict(debug_start_chapter=chapter)})
            state = CollectionState(mw)
            self.assertEqual(mw.get_region('Chapter 3', 1).can_reach(state), chapter == 3)
            self.assertFalse(mw.completion_condition[1](state))
            state.sweep_for_advancements()
            self.assertTrue(mw.completion_condition[1](state))
            self.assertFalse(any(state.has(i['name'], 1) for i in ITEMS))

    def test_added_rewards_replay_at_distinct_indexes(self):
        items = ITEMS[-4:]
        q = QueueModel(b'0123456789abcdef')
        q.save(0)
        for index in range(33):
            q.receive(q.identity, index, items[index % 4]['id'])
            q.receive(q.identity, index, items[index % 4]['id'])
        q.inventory = [1]*7
        q.player_phase()
        self.assertEqual(q.delivered, 0)
        received = []
        while q.delivered < 33:
            q.inventory.clear(); q.player_phase(); received.extend(q.inventory)
        self.assertEqual(received, [items[i % 4]['native'] for i in range(33)])
        q.load(0); q.player_phase()
        self.assertEqual(q.inventory, received[:7])


@unittest.skipUnless(os.getenv('FE5_BASE_ROM'), 'Private LM binary required')
class ChapterThreeBinaryTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(os.environ['FE5_BASE_ROM']).read_bytes()
        self.runtime = json.loads(Path(__file__).parents[1].joinpath('data/runtime.json').read_text())

    def test_chest_tokens_predicates_flags_and_ambush(self):
        for enabled in (0, 1):
            world = generate(options={1: dict(chestsanity=enabled, village_checks=enabled,
                                             fix_ambush_spawns=enabled, debug_start_chapter=3)}).worlds[1]
            seed = json.loads(make_seed_data(world)); rom = apply_patch(self.base, self.runtime, seed)
            for offset,native,token in ((0x18f5d5,0x16,0xac),(0x18f619,0x61,0xad)):
                self.assertEqual(rom[offset:offset+2], (token if enabled else native).to_bytes(2,'little'))
                self.assertEqual(rom[offset+2:offset+66], self.base[offset+2:offset+66])
            # Child predicates and repeatable fallback branches remain exact.
            self.assertEqual(rom[0x664b0:0x6668a], self.base[0x664b0:0x6668a])
            for offset in (0x66730,0x66867):
                self.assertEqual(rom[offset:offset+2], self.base[offset:offset+2])
            for offset in (0x66769,0x667ee):
                self.assertEqual(rom[offset:offset+41] == self.base[offset:offset+41], not enabled)
            for offset in (0x6645c,0x66473,0x6648a,0x664a1):
                self.assertEqual(rom[offset:offset+6], bytes.fromhex('06150e00')+(0 if enabled else 64).to_bytes(2,'little'))
            self.assertEqual(rom[0x66449:0x6644f], self.base[0x66449:0x6644f])
            self.assertEqual(rom[0x4a001c:0x4a0024], world.enabled_mask.to_bytes(8,'little'))

    def test_native_catalogue_and_debug_roster(self):
        world = generate(options={1: dict(debug_start_chapter=3)}).worlds[1]
        data = debug_units(self.base, world.debug_config, world.identity)
        self.assertEqual(len(data), 132)
        self.assertEqual(set(data[::12]), {1,2,5,3,4,8,6,37,9,32,11})
        self.assertEqual(data[1:3], bytes([3,10]))  # Leif gains 210 EXP.
        rom = apply_patch(self.base,self.runtime,json.loads(make_seed_data(world)))
        start = self.runtime['symbols']['ap_native_items'] - 0x148000 + 0x4a0000
        for i in ITEMS[-4:]:
            self.assertEqual(rom[start+i['native']*23:start+(i['native']+1)*23],
                             self.base[0x1800ab+i['native']*23:0x1800ab+(i['native']+1)*23])
        for native in (0xaa,0xab,0xac,0xad):
            entry = rom[start+native*23:start+(native+1)*23]
            self.assertEqual(entry[4], 1)
            self.assertEqual(entry[17:22], bytes([0,0,0,0,0x40]))
