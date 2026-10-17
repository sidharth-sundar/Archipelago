from argparse import Namespace
import unittest
from itertools import product
from BaseClasses import MultiWorld, CollectionState, ItemClassification
from worlds.AutoWorld import call_all
from Fill import distribute_items_restrictive
from importlib.resources import files
import yaml
from .. import FE5World
from ..definitions import ITEMS, LOCATIONS


def generate(players=1, seed=12345, options=None):
    mw = MultiWorld(players)
    mw.set_seed(seed)
    mw.seed_name = str(seed)
    mw.player_name = {}
    args = Namespace()
    for player in mw.player_ids:
        mw.game[player] = FE5World.game
        mw.player_name[player] = f"Thracia{player}"
    for name, option in FE5World.options_dataclass.type_hints.items():
        setattr(args, name, {p: option.from_any((options or {}).get(p, {}).get(name, option.default))
                             for p in mw.player_ids})
    mw.set_options(args)
    mw.state = CollectionState(mw)
    for stage in ("generate_early", "create_regions", "create_items", "set_rules"):
        call_all(mw, stage)
    distribute_items_restrictive(mw)
    return mw


class WorldTests(unittest.TestCase):
    def test_ids_pool_and_completion(self):
        mw = generate()
        self.assertEqual(len(FE5World.item_name_to_id), 18)
        self.assertEqual(len(set(FE5World.item_name_to_id.values())), 18)
        self.assertEqual(len(set(FE5World.location_name_to_id.values())), 17)
        houses = [l for l in mw.get_locations() if l.address is not None]
        self.assertEqual(len(houses), 16)
        self.assertCountEqual([l.item.name for l in houses], [i["name"] for i in ITEMS[:5]] + ["Nothing"] * 11)
        self.assertTrue(all(l.item.classification == (ItemClassification.filler if l.item.name == "Nothing"
                                                     else ItemClassification.useful) for l in houses))
        empty = CollectionState(mw)
        self.assertTrue(all(l.can_reach(empty) for l in mw.get_locations()))
        self.assertFalse(mw.completion_condition[1](empty))
        empty.sweep_for_advancements()
        self.assertTrue(mw.completion_condition[1](empty))
        self.assertFalse(any(empty.has(i["name"], 1) for i in ITEMS))

    def test_default_yaml(self):
        data = yaml.safe_load(files("worlds.fe5").joinpath("default.yaml").read_text())
        self.assertEqual(data["game"], FE5World.game)
        self.assertTrue(data[FE5World.game]["village_checks"])
        self.assertFalse(data[FE5World.game]["shopsanity"])
        self.assertEqual(data[FE5World.game]["shop_price_multiplier"], 1.0)
        self.assertTrue(data["name"])

    def test_deterministic_and_two_player_fill(self):
        def placements(mw):
            return [(l.player, l.name, l.item.player, l.item.name) for l in mw.get_locations()]
        one, two = generate(2), generate(2)
        self.assertEqual(placements(one), placements(two))
        self.assertEqual(len([l for l in one.get_locations() if l.address]), 32)
        self.assertTrue(one.can_beat_game())
        self.assertTrue(any(l.item.player != l.player for l in one.get_locations()))

    def test_all_option_combinations(self):
        keys = ("recruitment_checks", "village_checks", "conversation_checks", "chapter_completion_checks")
        for flags in product((False, True), repeat=4):
            with self.subTest(flags=flags):
                mw = generate(options={1: dict(zip(keys, flags))})
                world = mw.worlds[1]
                locations = [l for l in mw.get_locations() if l.address is not None]
                expected = sum(n for n, flag in zip((8, 5, 2, 1), flags) if flag)
                self.assertEqual(len(locations), expected)
                enabled = [l for l in LOCATIONS if dict(zip(keys, flags)).get(l["option"], False)]
                self.assertEqual({l.address for l in locations}, {l["id"] for l in enabled})
                self.assertEqual(world.fill_slot_data()["enabled_mask"], sum(1 << l["bit"] for l in enabled))
                self.assertEqual(sum(l.item.name != "Nothing" for l in locations), 5 if flags[1] else 0)
                self.assertTrue(mw.can_beat_game())

    def test_mixed_options(self):
        mw = generate(2, options={
            1: dict(conversation_checks=False, chapter_completion_checks=False),
            2: dict(recruitment_checks=False, village_checks=False)})
        self.assertEqual([len([l for l in mw.get_locations(p) if l.address]) for p in (1, 2)], [13, 3])
        self.assertEqual([mw.worlds[p].enabled_mask for p in (1, 2)], [0x1fff, 0xe000])
        self.assertEqual(sum(l.item.player == 2 and l.item.name != "Nothing"
                             for l in mw.get_locations() if l.address is not None), 0)
