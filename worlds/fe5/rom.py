"""Per-player seed patch and standard AP patch procedure."""
from importlib.resources import files
import json
import os
from pathlib import Path

from worlds.Files import APPatchExtension, APProcedurePatch
from .constants import GAME_NAME
from .definitions import PROTOCOL
from .patchcore import BASE_SHA1, apply_patch


def make_seed_data(world):
    return json.dumps({"protocol": PROTOCOL, "identity": world.identity.hex(), "slot": world.player,
                       "seed": world.multiworld.seed_name, "player": world.player_name,
                       "enabled_mask": world.enabled_mask, "shop_config": world.shop_config}, sort_keys=True).encode()


class FE5ProcedurePatch(APProcedurePatch):
    game = GAME_NAME
    hash = BASE_SHA1
    patch_file_ending = ".apfe5"
    result_file_ending = ".sfc"
    procedure = [("apply_fe5", [])]

    @classmethod
    def get_source_data(cls):
        path = os.environ.get("FE5_BASE_ROM")
        if not path:
            raise ValueError("Use FE5Patcher.exe to select your LM 1.08 ROM, or set FE5_BASE_ROM.")
        return Path(path).read_bytes()

    def add_runtime(self):
        self.write_file("runtime.json", files(__package__).joinpath("data/runtime.json").read_bytes())


class FE5PatchExtension(APPatchExtension):
    game = GAME_NAME

    @staticmethod
    def apply_fe5(patch, rom):
        return apply_patch(rom, json.loads(patch.get_file("runtime.json")), json.loads(patch.get_file("seed.json")))
