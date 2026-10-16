from argparse import Namespace
import unittest
from BaseClasses import MultiWorld, CollectionState, ItemClassification
from worlds.AutoWorld import call_all
from Fill import distribute_items_restrictive
from importlib.resources import files
import yaml
from .. import FE5World
from ..definitions import ITEMS, LOCATIONS


def generate(players=1, seed=12345):
    mw = MultiWorld(players)
    mw.set_seed(seed)
    mw.seed_name = str(seed)
    mw.player_name = {}
    args = Namespace()
    for player in mw.player_ids:
        mw.game[player] = FE5World.game
        mw.player_name[player] = f"Thracia{player}"
    for name, option in FE5World.options_dataclass.type_hints.items():
        setattr(args, name, {p: option.from_any(option.default) for p in mw.player_ids})
    mw.set_options(args)
    mw.state = CollectionState(mw)
    for stage in ("generate_early", "create_regions", "create_items", "set_rules"):
        call_all(mw, stage)
    distribute_items_restrictive(mw)
    return mw


class WorldTests(unittest.TestCase):
    def test_ids_pool_and_completion(self):
        mw = generate()
        self.assertEqual(len(FE5World.item_name_to_id), 5)
        self.assertEqual(len(set(FE5World.item_name_to_id.values())), 5)
        self.assertEqual(len(set(FE5World.location_name_to_id.values())), 5)
        houses = [l for l in mw.get_locations() if l.address is not None]
        self.assertEqual(len(houses), 5)
        self.assertCountEqual([l.item.name for l in houses], [i["name"] for i in ITEMS])
        self.assertTrue(all(l.item.classification == ItemClassification.useful for l in houses))
        empty = CollectionState(mw)
        self.assertTrue(all(l.can_reach(empty) for l in mw.get_locations()))
        self.assertFalse(mw.completion_condition[1](empty))
        empty.sweep_for_advancements()
        self.assertTrue(mw.completion_condition[1](empty))
        self.assertFalse(any(empty.has(i["name"], 1) for i in ITEMS))

    def test_default_yaml(self):
        data = yaml.safe_load(files("worlds.fe5").joinpath("default.yaml").read_text())
        self.assertEqual(data["game"], FE5World.game)
        self.assertEqual(data[FE5World.game], {})
        self.assertTrue(data["name"])

    def test_deterministic_and_two_player_fill(self):
        def placements(mw):
            return [(l.player, l.name, l.item.player, l.item.name) for l in mw.get_locations()]
        one, two = generate(2), generate(2)
        self.assertEqual(placements(one), placements(two))
        self.assertEqual(len([l for l in one.get_locations() if l.address]), 10)
        self.assertTrue(one.can_beat_game())
        self.assertTrue(any(l.item.player != l.player for l in one.get_locations()))
