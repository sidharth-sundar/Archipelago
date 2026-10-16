"""Chapter 1 of Fire Emblem: Thracia 776, on Lil' Manster 1.08."""
import base64
import hashlib
from pathlib import Path

from BaseClasses import ItemClassification, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from .constants import GAME_NAME
from .definitions import ITEMS, LOCATIONS, PROTOCOL
from .items import FE5Item
from .locations import FE5Location
from .options import FE5Options
from .rom import FE5ProcedurePatch, make_seed_data
from .client import FE5SNIClient


class FE5WebWorld(WebWorld):
    tutorials = [Tutorial("Setup", "Chapter 1 patch and SNI setup", "English",
                          "setup_en.md", "setup/en", ["sidharth-sundar"])]


class FE5World(World):
    """Five house rewards; seize with vanilla equipment to finish the game."""
    game = GAME_NAME
    web = FE5WebWorld()
    options_dataclass = FE5Options
    options: FE5Options
    item_name_to_id = {i["name"]: i["id"] for i in ITEMS}
    location_name_to_id = {l["name"]: l["id"] for l in LOCATIONS}

    def generate_early(self):
        self.identity = hashlib.sha256(
            f"FE5:{PROTOCOL}:{self.multiworld.seed_name}:{self.player}".encode()
        ).digest()[:16]

    def create_regions(self):
        menu = Region("Menu", self.player, self.multiworld)
        chapter = Region("Chapter 1", self.player, self.multiworld)
        self.multiworld.regions.extend([menu, chapter])
        menu.connect(chapter)
        chapter.add_locations(self.location_name_to_id, FE5Location)
        seize = FE5Location(self.player, "Chapter 1 - Seize", None, chapter)
        chapter.locations.append(seize)
        seize.place_locked_item(FE5Item("Victory", ItemClassification.progression, None, self.player))

    def create_items(self):
        self.multiworld.itempool += [self.create_item(i["name"]) for i in ITEMS]

    def create_item(self, name):
        return FE5Item(name, ItemClassification.useful, self.item_name_to_id[name], self.player)

    def get_filler_item_name(self):
        return "Vulnerary"

    def set_rules(self):
        # Tactical assumption, not an automated combat proof. Both special
        # visitors start available; seize also reports any missed houses.
        self.multiworld.completion_condition[self.player] = lambda state: state.has("Victory", self.player)

    def fill_slot_data(self):
        return {"protocol": PROTOCOL, "identity": self.identity.hex(), "chapter": 1}

    def modify_multidata(self, multidata):
        multidata["connect_names"][base64.b64encode(self.identity).decode()] = (
            multidata["connect_names"][self.multiworld.player_name[self.player]])

    def generate_output(self, output_directory):
        patch = FE5ProcedurePatch(player=self.player, player_name=self.player_name)
        patch.write_file("seed.json", make_seed_data(self))
        patch.add_runtime()
        patch.write(str(Path(output_directory) / (self.multiworld.get_out_file_name_base(self.player) + ".apfe5")))
