from collections import Counter
from copy import deepcopy
import json
from random import Random
import unittest

from ..extra_items import BOOSTERS, STAVES, DEFAULTS, resolve_extra_items, extra_config_bytes
from ..definitions import ITEMS
from ..options import FE5Options
from ..protocol import QueueModel, encode_receipt, decode_receipt, ProtocolError
from ..rom import make_seed_data
from .test_world import generate


def counts(world):
    return Counter(loc.item.name for loc in world.get_locations() if loc.address is not None)


class ExtraItemTests(unittest.TestCase):
    def resolve(self, **values):
        return resolve_extra_items(DEFAULTS | values, Random(42))

    def test_disabled_is_identical_to_default(self):
        disabled = {key: 9 for key in BOOSTERS} | {key: 3 for key in STAVES}
        disabled.update(random_stat_boosters=1, random_stat_booster_count=9,
                        exclude_boots_from_random_stat_boosters=1)
        one, two = generate(), generate(options={1: disabled})
        self.assertEqual(counts(one), counts(two))
        self.assertEqual(one.worlds[1].identity, two.worlds[1].identity)
        self.assertEqual(one.worlds[1].extra_items, two.worlds[1].extra_items)

    def test_counts_ranges(self):
        for key in (*BOOSTERS, *STAVES, 'random_stat_booster_count'):
            option = FE5Options.type_hints[key]
            maximum = 3 if key in STAVES else 9
            for value in (0, maximum):
                with self.subTest(option=key, value=value):
                    self.assertEqual(option.from_any(value).value, value)
            for value in (-1, maximum + 1):
                with self.subTest(option=key, value=value), self.assertRaises(Exception):
                    option.from_any(value)

    def test_manual_all_items_and_exact_capacity(self):
        settings = dict(enable_extra_valuable_items=1, shopsanity=1)
        settings.update(dict.fromkeys(BOOSTERS | STAVES, 1))
        mw = generate(options={1: settings})
        pool = counts(mw)
        self.assertEqual(sum(pool.values()), 17)
        self.assertEqual(pool['Nothing'], 0)
        self.assertEqual(pool['Life Ring'], 2)
        self.assertEqual(pool['Vulnerary'], 2)
        for name in (BOOSTERS | STAVES).values():
            self.assertGreaterEqual(pool[name], 1)
        seed = json.loads(make_seed_data(mw.worlds[1]))
        self.assertEqual(seed['extra_items'], mw.worlds[1].fill_slot_data()['extra_items'])

    def test_random_precedence_duplicate_draws_and_independent_staves(self):
        values = dict(enable_extra_valuable_items=1, random_stat_boosters=1,
                      random_stat_booster_count=9, exclude_boots_from_random_stat_boosters=1,
                      extra_warp_staves=2, extra_rescue_staves=3)
        a = self.resolve(**values)
        b = self.resolve(**(values | dict.fromkeys(BOOSTERS, 9)))
        self.assertEqual(a, b)
        resolved = a['resolved_counts']
        self.assertEqual(sum(resolved[n] for n in BOOSTERS.values()), 9)
        self.assertEqual(resolved['Boots'], 0)
        self.assertTrue(any(resolved[n] > 1 for n in BOOSTERS.values()))
        self.assertEqual((resolved['Warp'], resolved['Rescue']), (2, 3))
        manual = self.resolve(enable_extra_valuable_items=1, extra_boots=2,
                              exclude_boots_from_random_stat_boosters=1, random_stat_booster_count=9)
        self.assertEqual(manual['resolved_counts']['Boots'], 2)
        self.assertEqual(manual['random_stat_booster_count'], 0)

    def test_seeded_random_generation_and_two_players(self):
        options = {1: dict(enable_extra_valuable_items=1, random_stat_boosters=1,
                           random_stat_booster_count=7, extra_warp_staves=2),
                   2: dict(enable_extra_valuable_items=1, extra_rescue_staves=3)}
        a, b = generate(2, options=options), generate(2, options=options)
        self.assertEqual([(l.name, l.item.name, l.item.player) for l in a.get_locations()],
                         [(l.name, l.item.name, l.item.player) for l in b.get_locations()])
        self.assertTrue(any(l.player != l.item.player for l in a.get_locations()))
        self.assertTrue(a.can_beat_game())

    def test_below_exact_and_overflow_by_player(self):
        for amount, filler in ((8, 3), (9, 2)):
            mw = generate(options={1: dict(enable_extra_valuable_items=1, extra_boots=amount)})
            self.assertEqual(counts(mw)['Nothing'], filler)
        exact = dict(enable_extra_valuable_items=1, extra_boots=9, extra_warp_staves=2)
        self.assertEqual(counts(generate(options={1: exact}))['Nothing'], 0)
        for player in (1, 2):
            with self.subTest(player=player), self.assertRaisesRegex(
                    ValueError, rf'Thracia{player}: 16 enabled locations, 5 existing rewards \+ 12 extra rewards; exceeds capacity by 1'):
                generate(2, options={player: exact | {'extra_warp_staves': 3}})

    def test_disabled_categories_and_zero_locations(self):
        no_checks = dict(recruitment_checks=0, village_checks=0, conversation_checks=0,
                         chapter_completion_checks=0, shopsanity=0)
        self.assertEqual(sum(counts(generate(options={1: no_checks})).values()), 0)
        with self.assertRaisesRegex(ValueError, '0 enabled locations, 0 existing rewards.*by 1'):
            generate(options={1: no_checks | dict(enable_extra_valuable_items=1, extra_boots=1)})
        small = no_checks | dict(conversation_checks=1, enable_extra_valuable_items=1, extra_rescue_staves=2)
        self.assertEqual(counts(generate(options={1: small})), Counter({'Rescue': 2}))
        with self.assertRaisesRegex(ValueError, '2 enabled locations.*by 1'):
            generate(options={1: small | dict(extra_rescue_staves=3)})

    def test_effective_identity_and_config_validation(self):
        a = generate().worlds[1]
        b = generate(options={1: dict(enable_extra_valuable_items=1, extra_boots=1)}).worlds[1]
        self.assertNotEqual(a.identity, b.identity)
        self.assertNotEqual(extra_config_bytes(a.extra_items), extra_config_bytes(b.extra_items))
        broken = deepcopy(b.extra_items)
        broken['resolved_counts']['Boots'] = 2
        with self.assertRaises(ValueError):
            extra_config_bytes(broken)
        for bad in (None, {}, {'enable_extra_valuable_items': 1}):
            with self.assertRaises(ValueError):
                extra_config_bytes(bad)

    def test_new_items_order_duplicates_wrap_and_replay(self):
        items = [i for i in ITEMS if i['name'] in (BOOSTERS | STAVES).values()]
        q = QueueModel(b'0123456789abcdef')
        q.save(0)
        for index in range(33):
            item = items[index % len(items)]
            packet = encode_receipt(index, item['id'])
            self.assertEqual(decode_receipt(packet, index), item['native'])
            self.assertIsNone(decode_receipt(packet[:5], index))
            q.receive(q.identity, index, item['id'])
            q.receive(q.identity, index, item['id'])
        q.inventory = [1] * 7
        q.player_phase()
        self.assertEqual(q.delivered, 0)
        seen = []
        while q.delivered < 33:
            q.inventory.clear()
            q.player_phase()
            seen.extend(q.inventory)
        self.assertEqual(seen, [items[i % len(items)]['native'] for i in range(33)])
        q.load(0)
        self.assertEqual(q.delivered, 0)
        q.player_phase()
        self.assertEqual(q.inventory, seen[:7])
        with self.assertRaises(ProtocolError):
            encode_receipt(0, 123)

    def test_stable_existing_ids(self):
        self.assertEqual([i['id'] for i in ITEMS[:6]], list(range(16666624, 16666630)))
        self.assertEqual(len({i['native'] for i in ITEMS}), 16)


if __name__ == '__main__':
    unittest.main()
