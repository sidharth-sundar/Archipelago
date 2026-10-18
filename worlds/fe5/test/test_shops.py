import copy
import json
import unittest
from itertools import product
from importlib.resources import files
from ..definitions import HISTORY_CAPACITY, PENDING_CAPACITY, ITEMS, LOCATIONS
from ..options import PriceMultiplier
from ..patchcore import purchase_price, shop_config_bytes
from ..protocol import QueueModel, encode_receipt, decode_receipt, ProtocolError, checks_for
from .test_world import generate


class ShopWorldTests(unittest.TestCase):
    def test_every_toggle_combination(self):
        keys = ('recruitment_checks', 'village_checks', 'conversation_checks',
                'chapter_completion_checks', 'shopsanity', 'shop_items_in_pool',
                'armorysanity', 'armory_items_in_pool')
        for flags in product((False, True), repeat=len(keys)):
            opts = dict(zip(keys, flags))
            with self.subTest(opts=opts):
                mw = generate(options={1: opts})
                world = mw.worlds[1]
                locations = [l for l in mw.get_locations() if l.address is not None]
                count = sum(size * flag for size, flag in zip((9, 8, 2, 2, 2), flags))
                physical = 7 * opts['village_checks'] + 2 * (opts['shopsanity'] and opts['shop_items_in_pool'])
                self.assertEqual(len(locations), count)
                self.assertEqual(sum(l.item.name != 'Nothing' for l in locations), physical)
                self.assertEqual(sum(l.item.name == 'Vulnerary' for l in locations),
                                 2 * opts['village_checks'] + 2 * int(opts['shopsanity'] and opts['shop_items_in_pool']))
                self.assertTrue(mw.can_beat_game())
                self.assertEqual(set(checks_for(0, True, world.enabled_mask)), {l.address for l in locations})

    def test_multiplier_parsing_and_floor_bargain(self):
        for tenths in range(1, 101):
            for value in (str(tenths / 10), tenths / 10):
                self.assertEqual(PriceMultiplier.from_any(value).value, tenths)
            self.assertEqual(purchase_price(603, tenths), 603 * tenths // 10)
            self.assertEqual(purchase_price(603, tenths, True), (603 * tenths // 10) // 2)
        for value in (0, -1, 10.1, 0.15, True, 'nan', 'inf', 'one'):
            with self.assertRaises(Exception):
                PriceMultiplier.from_any(value)
        self.assertEqual(purchase_price(600, 4), 240)
        with self.assertRaises(ValueError):
            purchase_price(10000, 100)

    def test_identity_configuration_and_determinism(self):
        one = generate(2, options={1: dict(shopsanity=True, shop_price_multiplier=0.4),
                                   2: dict(village_checks=False, shopsanity=True, shop_items_in_pool=False)})
        two = generate(2, options={1: dict(shopsanity=True, shop_price_multiplier=0.4),
                                   2: dict(village_checks=False, shopsanity=True, shop_items_in_pool=False)})
        self.assertEqual([(l.player, l.name, l.item.name, l.item.player) for l in one.get_locations()],
                         [(l.player, l.name, l.item.name, l.item.player) for l in two.get_locations()])
        self.assertNotEqual(generate().worlds[1].identity,
                            generate(options={1: dict(shop_price_multiplier=0.4)}).worlds[1].identity)
        self.assertEqual(len(shop_config_bytes(one.worlds[1].shop_config)), 6)
        for name, value in [('shopsanity', 2), ('shop_price_multiplier', 101)]:
            invalid = dict(one.worlds[1].shop_config, **{name: value})
            with self.assertRaises(ValueError):
                shop_config_bytes(invalid)


class ReceiptBitmapTests(unittest.TestCase):
    def test_all_history_entries_ring_wrap_and_offline_replay(self):
        q = QueueModel(b'0123456789abcdef')
        q.save(0)
        for index in range(HISTORY_CAPACITY):
            q.receive(q.identity, index, next(i for i in ITEMS if i["name"] == "Nothing")['id'])
        q.player_phase(False)
        self.assertEqual(q.delivered, 1024)
        self.assertEqual(q.processed, 1024)
        self.assertEqual(q.applied, b'\xff' * 128)
        self.assertEqual(q.pending, [])
        q.save(1)
        q.load(0)
        self.assertEqual(q.applied, bytes(128))
        q.player_phase(False)
        self.assertEqual(q.delivered, 1024)
        q.load(1)
        q.player_phase()
        self.assertEqual(q.delivered, 1024)
        with self.assertRaises(ProtocolError):
            q.receive(q.identity, 1024, next(i for i in ITEMS if i["name"] == "Nothing")['id'])

    def test_repeated_types_distinct_receipts_and_applied_replay(self):
        q = QueueModel(b'0123456789abcdef')
        vuln = ITEMS[2]
        for i in range(33):
            q.receive(q.identity, i, vuln['id'] if i in (0, 16, 32) else next(i for i in ITEMS if i["name"] == "Nothing")['id'])
        q.inventory = [99] * 7
        q.player_phase()
        self.assertEqual(len(q.pending), PENDING_CAPACITY)
        self.assertEqual(q.applied, bytes(128))
        q.inventory = []
        q.player_phase()
        self.assertEqual(q.inventory, [vuln['native']] * 3)
        q.save(0)
        q.copy(0, 1)
        q.delete(0)
        q.load(1)
        q.player_phase()
        self.assertEqual(q.inventory, [vuln['native']] * 3)
        # An already-applied receipt in the pending ring is skipped safely.
        q.delivered = 32
        q.pending = [vuln['native']]
        q.player_phase()
        self.assertEqual(q.inventory, [vuln['native']] * 3)

    def test_full_width_commit_and_torn_final_record(self):
        for index in (0, 16, 255, 256, 1023):
            packet = encode_receipt(index, ITEMS[2]['id'])
            self.assertEqual(decode_receipt(packet, index), ITEMS[2]['native'])
            for size in range(8):
                self.assertIsNone(decode_receipt(packet[:size] + bytes(8 - size), index))
        self.assertIsNone(decode_receipt(encode_receipt(255, ITEMS[2]['id']), 256))

    def test_sram_ranges_and_full_companion_bitmap(self):
        runtime = json.loads(files('worlds.fe5').joinpath('data/runtime.json').read_bytes())
        symbols = runtime['symbols']
        self.assertEqual(symbols['ap_applied'] + 128, symbols['ap_live'] + 256)
        self.assertLessEqual(symbols['ap_arrivals'] + HISTORY_CAPACITY * 8, 0x718000)
        self.assertLessEqual(symbols['ap_companions'] + 1024, symbols['ap_arrivals'])
