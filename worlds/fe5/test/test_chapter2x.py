from collections import Counter
from itertools import product
import json
import os
from pathlib import Path
import unittest

from ..definitions import ITEMS, LOCATIONS, PROTOCOL
from ..options import DebugStartChapter
from ..patchcore import valid_mask, apply_patch
from ..protocol import QueueModel, checks_for
from ..rom import make_seed_data
from .test_world import generate


class ChapterTwoXTests(unittest.TestCase):
    def test_all_check_category_combinations(self):
        keys = ('recruitment_checks', 'village_checks', 'conversation_checks',
                'chapter_completion_checks', 'shopsanity', 'ground_pickup',
                'capturesanity_easy', 'capturesanity_hard', 'chestsanity', 'blue_escapesanity', 'green_escapesanity')
        for flags in product((0, 1), repeat=len(keys)):
            with self.subTest(flags=flags):
                opts = dict(zip(keys, flags))
                mw = generate(options={1: opts})
                world = mw.worlds[1]
                locations = [l for l in mw.get_locations() if l.address is not None]
                expected = sum(a*b for a,b in zip((17,12,4,5,4,2,1,1,6,5,6),flags))
                pool = Counter(l.item.name for l in locations)
                self.assertEqual(len(locations), expected)
                self.assertEqual(pool['Torch'], flags[5]*2)
                physical = flags[1]*9 + flags[4]*4 + flags[5]*2 + flags[8]*6
                self.assertEqual(pool['Nothing'], expected-physical)
                self.assertTrue(valid_mask(world.enabled_mask))
                self.assertEqual(set(checks_for(0, True, world.enabled_mask)), {l.address for l in locations})
                self.assertTrue(mw.can_beat_game())

    def test_full_pool_and_token_identity(self):
        mw = generate(options={1: dict(shopsanity=1, capturesanity_easy=1, capturesanity_hard=1)})
        self.assertEqual(mw.worlds[1].enabled_mask, (1 << 63)-1)
        pool = Counter(l.item.name for l in mw.get_locations() if l.address)
        self.assertEqual(sum(pool.values()),63)
        self.assertEqual(pool['Nothing'],42)
        self.assertEqual([l['id'] for l in LOCATIONS], list(range(16666880,16666943)))
        self.assertEqual([l['token_native'] for l in LOCATIONS if 'token_native' in l],list(range(0xaa,0xb2)))
        self.assertFalse({0xaa,0xab,0xac,0xad} & {i['native'] for i in ITEMS})

    def test_debug_and_ambush_configuration(self):
        self.assertEqual(DebugStartChapter.from_any('2x').value,3)
        normal = generate().worlds[1]
        for option in ('fix_ambush_spawns','capturesanity_easy','capturesanity_hard'):
            changed = generate(options={1:{option:1}}).worlds[1]
            self.assertNotEqual(normal.identity,changed.identity)
            self.assertEqual(json.loads(make_seed_data(changed))['fix_ambush_spawns'],changed.fill_slot_data()['fix_ambush_spawns'])
        self.assertEqual(PROTOCOL,11)

    def test_torch_receipt_replay_and_full_inventory(self):
        torch = next(i for i in ITEMS if i['name']=='Torch')
        self.assertEqual((torch['native'],torch['durability']),(0x8f,1))
        q=QueueModel(b'0123456789abcdef')
        q.save(0)
        for index in range(17):
            q.receive(q.identity,index,torch['id'])
            q.receive(q.identity,index,torch['id'])
        q.inventory=[1]*7
        q.player_phase()
        self.assertEqual(q.delivered,0)
        while q.delivered<17:
            q.inventory.clear();q.player_phase()
        q.load(0)
        q.player_phase()
        self.assertEqual(q.delivered,7)

    @unittest.skipUnless(os.getenv('FE5_BASE_ROM'),'Private LM binary required')
    def test_conditional_hooks_and_old_protocol_rejection(self):
        base=Path(os.environ['FE5_BASE_ROM']).read_bytes()
        runtime=json.loads(Path(__file__).parents[1].joinpath('data/runtime.json').read_text())
        phase_offsets=(0xc81d9,0xc81ec,0xc81ff,0xb80a5,0xb80b8,0xb80d1,0xb80e8)
        for enabled in (0,1):
            seed=json.loads(make_seed_data(generate(options={1:dict(fix_ambush_spawns=enabled,ground_pickup=enabled,capturesanity_easy=enabled,capturesanity_hard=enabled)}).worlds[1]))
            rom=apply_patch(base,runtime,seed)
            for offset in phase_offsets:
                self.assertEqual(rom[offset:offset+6],bytes.fromhex('06150e00')+(0 if enabled else 64).to_bytes(2,'little'))
            for offset in (0xb806e,0xb807f,0xb8094):
                self.assertEqual(rom[offset:offset+6],base[offset:offset+6])
            for offset,native in ((0x18f679,0xaa),(0x18f68d,0xab)):
                self.assertEqual(rom[offset:offset+2],bytes([native if enabled else 0,0]))
            self.assertEqual(rom[0xb8368:0xb838f]==base[0xb8368:0xb838f],not enabled)
            self.assertEqual(rom[0x4a0050:0x4a0052],enabled.to_bytes(2,'little'))
            # Appended source tokens occupy consecutive native stock bytes;
            # their strings must remain outside the alphabetical sort table.
            for offset in (0x18f66f,0x18f683):
                self.assertEqual(rom[offset+11:offset+15],bytes(4))
            self.assertEqual(rom[0x187600+0xaa*2:0x187600+0xac*2],bytes.fromhex('40 fa 40 fa'))
            self.assertEqual(rom[0x187a40:0x187a44],bytes.fromhex('82 60 82 6f'))
            with self.assertRaises(ValueError):apply_patch(base,runtime,seed|{'protocol':8})
            with self.assertRaises(ValueError):apply_patch(base,runtime,seed|{'fix_ambush_spawns':2})
