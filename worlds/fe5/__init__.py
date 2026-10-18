"""Chapters 1 through 3 of Fire Emblem: Thracia 776 on Lil' Manster 1.08."""
import base64
import hashlib
import json
from pathlib import Path

from BaseClasses import ItemClassification, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from .constants import GAME_NAME
from .definitions import ITEMS, LOCATIONS, PROTOCOL, HISTORY_CAPACITY, STORES
from .items import FE5Item
from .locations import FE5Location
from .options import FE5Options, extra_option_groups
from .extra_items import DEFAULTS, resolve_extra_items
from .rom import FE5ProcedurePatch, make_seed_data
from .debug import debug_config_bytes
from .client import FE5SNIClient
from .effects import DEFAULTS as EFFECT_DEFAULTS, WEIGHTS, HARMFUL, choose_filler, effect_config_bytes


class FE5WebWorld(WebWorld):
    option_groups = extra_option_groups
    tutorials = [Tutorial("Setup", "Chapters 1 through 3 patch and SNI setup", "English",
                          "setup_en.md", "setup/en", ["sidharth-sundar"])]


class FE5World(World):
    """Optional checks through Chapter 3; seize Chapter 3 to finish."""
    game = GAME_NAME
    web = FE5WebWorld()
    options_dataclass = FE5Options
    options: FE5Options
    item_name_to_id = {i["name"]: i["id"] for i in ITEMS}
    location_name_to_id = {l["name"]: l["id"] for l in LOCATIONS}

    def generate_early(self):
        self.enabled_locations = [l for l in LOCATIONS if getattr(self.options, l["option"]).value]
        self.enabled_mask = sum(1 << l["bit"] for l in self.enabled_locations)
        self.shop_config = {name: getattr(self.options, name).value for name in (
            "armorysanity", "armory_items_in_pool", "armory_price_multiplier",
            "shopsanity", "shop_items_in_pool", "shop_price_multiplier")}
        self.extra_items = resolve_extra_items(
            {name: getattr(self.options, name).value for name in DEFAULTS}, self.random)
        self.effects = {name: getattr(self.options, name).value for name in EFFECT_DEFAULTS}
        effect_config_bytes(self.effects)
        self.debug_config = {name: getattr(self.options, name).value for name in (
            "debug_start_chapter", "debug_exp_per_chapter", "debug_growth_mode")}
        debug_config_bytes(self.debug_config)
        self.fix_ambush_spawns = self.options.fix_ambush_spawns.value
        self.identity = hashlib.sha256(
            json.dumps(["FE5", PROTOCOL, self.multiworld.seed_name, self.player,
                        self.enabled_mask, self.shop_config, self.extra_items, self.effects, self.debug_config, self.fix_ambush_spawns], sort_keys=True).encode()
        ).digest()[:16]

    def create_regions(self):
        menu = Region("Menu", self.player, self.multiworld)
        chapters = {n: Region(f"Chapter {n}", self.player, self.multiworld) for n in (1, 2, "2x", 3)}
        self.multiworld.regions.extend([menu, *chapters.values()])
        menu.connect(chapters[1])
        chapters[1].connect(chapters[2], rule=lambda state: state.has("Chapter 1 Cleared", self.player))
        chapters[2].connect(chapters["2x"], rule=lambda state: state.has("Chapter 2 Cleared", self.player))
        chapters[2].connect(chapters[3], "Native Chapter 2 skip", rule=lambda state: state.has("Chapter 2 Cleared", self.player))
        chapters["2x"].connect(chapters[3], rule=lambda state: state.has("Chapter 2x Cleared", self.player))
        if self.debug_config["debug_start_chapter"] == 4:
            menu.connect(chapters[3], "Debug Chapter 3 Start")
        if self.debug_config["debug_start_chapter"] == 3:
            menu.connect(chapters["2x"], "Debug Chapter 2x Start")
        if self.debug_config["debug_start_chapter"] == 2:
            menu.connect(chapters[2], "Debug Chapter 2 Start")
        for n, chapter in chapters.items():
            chapter.add_locations({l["name"]: l["id"] for l in self.enabled_locations if l["chapter"] == n}, FE5Location)
            seize = FE5Location(self.player, f"Chapter {n} - Seize", None, chapter)
            chapter.locations.append(seize)
            seize.place_locked_item(FE5Item(f"Chapter {n} Cleared" if n != 3 else "Victory",
                                          ItemClassification.progression, None, self.player))

    def create_items(self):
        rewards = [next(i["name"] for i in ITEMS if i["native"] == location["reward_native"])
                   for location in self.enabled_locations if "reward_native" in location]
        for store in STORES:
            category = store["category"]
            if (getattr(self.options, category + "sanity")
                    and getattr(self.options, category + "_items_in_pool")):
                rewards.extend(slot["item"] for slot in store["slots"])
        existing_count = len(rewards)
        extras = [name for name, count in self.extra_items["resolved_counts"].items() for _ in range(count)]
        rewards += extras
        if len(rewards) > len(self.enabled_locations):
            raise ValueError(f"FE5 player {self.player_name}: {len(self.enabled_locations)} enabled locations, "
                             f"{existing_count} existing rewards + {len(extras)} extra rewards; "
                             f"exceeds capacity by {len(rewards) - len(self.enabled_locations)}. "
                             "Enable more check categories or reduce extra item counts.")
        if len(self.enabled_locations) > HISTORY_CAPACITY:
            raise ValueError("FE5 enabled locations exceed receipt history capacity")
        rewards += [self.get_filler_item_name() for _ in range(len(self.enabled_locations) - len(rewards))]
        self.multiworld.itempool += [self.create_item(name) for name in rewards]

    def create_item(self, name):
        classification = (ItemClassification.trap if name in HARMFUL else
                          ItemClassification.filler if name == "Nothing" or name in WEIGHTS.values()
                          else ItemClassification.useful)
        return FE5Item(name, classification, self.item_name_to_id[name], self.player)

    def get_filler_item_name(self):
        return choose_filler(self.effects, self.random)

    def set_rules(self):
        # Tactical assumption, not an automated combat proof. Both special
        # visitors start available; final seizure reports all missed checks.
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def fill_slot_data(self):
        return {"protocol": PROTOCOL, "identity": self.identity.hex(), "chapter": 3, "fix_ambush_spawns": self.fix_ambush_spawns, "debug_config": self.debug_config,
                "enabled_mask": self.enabled_mask, "shop_config": self.shop_config, "extra_items": self.extra_items, "effects": self.effects}

    def modify_multidata(self, multidata):
        multidata["connect_names"][base64.b64encode(self.identity).decode()] = (
            multidata["connect_names"][self.multiworld.player_name[self.player]])

    def generate_output(self, output_directory):
        patch = FE5ProcedurePatch(player=self.player, player_name=self.player_name)
        patch.write_file("seed.json", make_seed_data(self))
        patch.add_runtime()
        patch.write(str(Path(output_directory) / (self.multiworld.get_out_file_name_base(self.player) + ".apfe5")))
