import copy
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from ..definitions import ITEMS, LOCATIONS, PROTOCOL
from ..patchcore import BASE_SHA1, apply_patch, patch_file
from ..rom import make_seed_data
from .test_world import generate


class PatchTests(unittest.TestCase):
    def test_generated_ids_match_packaged_source(self):
        schema = json.loads(files("worlds.fe5").joinpath("data/schema.json").read_bytes())
        self.assertEqual(ITEMS, schema["items"])
        self.assertEqual(LOCATIONS, schema["locations"])

    def test_wrong_base_rejected(self):
        with self.assertRaisesRegex(ValueError, "unmodified"):
            apply_patch(bytes(0x600000), {}, {})

    def test_generation_emits_patch_with_runtime_resources(self):
        mw = generate()
        with tempfile.TemporaryDirectory() as directory:
            mw.worlds[1].generate_output(directory)
            patches = list(Path(directory).glob("*.apfe5"))
            self.assertEqual(len(patches), 1)
            with zipfile.ZipFile(patches[0]) as archive:
                self.assertEqual(set(archive.namelist()), {"archipelago.json", "runtime.json", "seed.json"})
                seed = json.loads(archive.read("seed.json"))
                self.assertEqual(seed["identity"], mw.worlds[1].identity.hex())

    def test_allocations_and_symbols(self):
        runtime = json.loads(files("worlds.fe5").joinpath("data/runtime.json").read_bytes())
        self.assertEqual(runtime["symbols"]["ap_header"], 0x148000)
        self.assertLess(runtime["symbols"]["ap_end"], 0x158000)
        ranges = sorted((w["offset"], w["offset"] + len(bytes.fromhex(w["data"]))) for w in runtime["writes"])
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(ranges, ranges[1:])))
        self.assertTrue(all(0 <= start < end <= 0x600000 for start, end in ranges))
        symbols = runtime['symbols']
        self.assertEqual(symbols['ap_companion_size'], 1024)
        self.assertLessEqual(symbols['ap_fcm_bonus'] + 512, symbols['ap_live'] + 1024)
        self.assertEqual(symbols['ap_companions'] + 4 * 1024, symbols['ap_arrivals'])

    def test_generated_queue_addresses_are_complete(self):
        from .. import connector_config as config
        runtime = json.loads(files("worlds.fe5").joinpath("data/runtime.json").read_bytes())
        # 64tass prints arithmetic aliases in decimal; these must survive export.
        for name in ("AP_PROCESSED", "AP_DELIVERED", "AP_SAVED", "AP_PENDING", "AP_EFFECT_CONSUMED", "AP_EFFECT_PENDING", "AP_EFFECT_SCAN", "AP_PHASE_LIMIT", "AP_ACTIVE_EFFECT"):
            bus = runtime["symbols"][name.lower()]
            expected = 0xe00000 + ((bus >> 16) - 0x70) * 0x8000 + (bus & 0x7fff)
            self.assertEqual(getattr(config, name), expected)
        self.assertEqual(config.AP_DELIVERED, config.AP_PROCESSED + 2)
        self.assertEqual(config.AP_SAVED, config.AP_PROCESSED + 4)
        self.assertEqual(config.AP_PENDING, config.AP_PROCESSED + 0x20)


@unittest.skipUnless(os.environ.get("FE5_BASE_ROM"), "Local integration test requires the private LM 1.08 ROM")
class PrivateROMPatchTests(unittest.TestCase):
    def setUp(self):
        self.base_path = Path(os.environ["FE5_BASE_ROM"])
        self.base = self.base_path.read_bytes()
        self.runtime = json.loads(files("worlds.fe5").joinpath("data/runtime.json").read_bytes())
        self.seed = json.loads(make_seed_data(generate().worlds[1]))

    def test_real_patch_and_source_unchanged(self):
        result = apply_patch(self.base, self.runtime, self.seed)
        self.assertEqual(len(result), len(self.base))
        self.assertEqual(result[0x4a0000:0x4a0008], b"FE5AP009")
        self.assertEqual(result[0x7fd8], 7)
        self.assertEqual(result[0x407fd8], 7)
        self.assertEqual(hashlib.sha1(self.base_path.read_bytes()).hexdigest(), BASE_SHA1)
        # Both character-specific visitor predicates, phase/coordinate gates,
        # wrong-visitor paths and legitimate seizure predicate remain native.
        self.assertEqual(result[0x3e803d:0x3e80e5], self.base[0x3e803d:0x3e80e5])

    def test_expected_bytes_and_allocation_rejected(self):
        broken = copy.deepcopy(self.runtime)
        broken["writes"][0]["expected"] = "00" * (len(broken["writes"][0]["expected"]) // 2)
        with self.assertRaisesRegex(ValueError, "Original-byte"):
            apply_patch(self.base, broken, self.seed)
        broken = copy.deepcopy(self.runtime)
        broken["writes"][-1]["zero_length"] += 1
        with self.assertRaisesRegex(ValueError, "allocation"):
            apply_patch(self.base, broken, self.seed)

    def test_atomic_file_and_reject_source_as_output(self):
        mw = generate()
        with tempfile.TemporaryDirectory() as directory:
            mw.worlds[1].generate_output(directory)
            patch = next(Path(directory).glob("*.apfe5"))
            out = Path(directory) / "patched.sfc"
            patch_file(self.base_path, patch, out)
            self.assertEqual(out.stat().st_size, 0x600000)
            self.assertEqual(list(Path(directory).glob(".fe5-*")), [])
            with self.assertRaisesRegex(ValueError, "differ"):
                patch_file(self.base_path, patch, self.base_path)

    def test_village_off_preserves_native_grants(self):
        self.seed["enabled_mask"] = 0x640e000
        result = apply_patch(self.base, self.runtime, self.seed)
        for location in LOCATIONS[:5]:
            start = location["event"]
            self.assertEqual(result[start:start+99], self.base[start:start+99])
        self.assertEqual(result[0x4a001c:0x4a001e], b"\0\xe0")

    def test_music_hook_preserves_native_song_scripts(self):
        result = apply_patch(self.base, self.runtime, self.seed)
        # Changing the shared boss script would also change actual boss battles.
        self.assertEqual(result[0x2d8000:0x2e0000], self.base[0x2d8000:0x2e0000])
        hook = next(w for w in self.runtime['writes'] if w['name'] == 'AP boss field playback command')
        broken = copy.deepcopy(self.runtime)
        next(w for w in broken['writes'] if w['name'] == hook['name'])['expected'] = '00000000'
        with self.assertRaisesRegex(ValueError, 'Original-byte'):
            apply_patch(self.base, broken, self.seed)

    def test_protocol_and_partial_category_mask_rejected(self):
        for key, value in (("protocol", 1), ("protocol", 3), ("protocol", 4), ("enabled_mask", 1), ("enabled_mask", 65536)):
            seed = dict(self.seed, **{key: value})
            with self.assertRaises(ValueError):
                apply_patch(self.base, self.runtime, seed)

    def test_new_native_items_and_configuration_digest(self):
        from ..extra_items import extra_config_bytes
        from ..connector_config import HEADER_SIZE
        seed = json.loads(make_seed_data(generate(options={1: {
            'enable_extra_valuable_items': 1, 'extra_warp_staves': 1,
            'random_stat_boosters': 1, 'random_stat_booster_count': 8}}).worlds[1]))
        result = apply_patch(self.base, self.runtime, seed)
        self.assertEqual(HEADER_SIZE, 78)
        from ..effects import effect_config_bytes
        self.assertEqual(result[0x4a0036:0x4a0046], effect_config_bytes(seed['effects']))
        self.assertEqual(result[0x4a0026:0x4a0036], extra_config_bytes(seed['extra_items']))
        physical = [i for i in ITEMS if 'durability' in i]
        start = self.runtime['symbols']['ap_item_table'] - 0x148000 + 0x4a0000
        table = b''.join(i['native'].to_bytes(2, 'little') +
                         ((i['durability'] << 8) | i['native']).to_bytes(2, 'little') for i in physical)
        self.assertEqual(result[start:start+len(table)], table)
        for item in physical:
            self.assertEqual(result[self.runtime['symbols']['ap_native_items'] - 0x148000 + 0x4a0000 + 23 * item['native'] + 4], item['durability'])
        broken = copy.deepcopy(seed)
        broken['extra_items']['resolved_counts']['Warp'] = 0
        with self.assertRaisesRegex(ValueError, 'Staff/manual configuration'):
            apply_patch(self.base, self.runtime, broken)

    def test_appended_native_tables_preserve_vanilla_and_manual_dispatch(self):
        result = apply_patch(self.base, self.runtime, self.seed)
        start = self.runtime['symbols']['ap_native_items'] - 0x148000 + 0x4a0000
        self.assertEqual(result[start:start+168*23], self.base[0x1800ab:0x1800ab+168*23])
        self.assertEqual(result[0x187600:0x187750], self.base[0x180fc3:0x181113])
        self.assertEqual(result[0x187900:0x1879a8], self.base[0x18192e:0x1819d6])
        for item in (168, 169):
            entry = result[start+item*23:start+(item+1)*23]
            self.assertEqual(entry[4], 1)
            self.assertEqual(entry[17], 0x28)  # native manual sequence
            self.assertEqual(entry[18:22], bytes(4))  # no passive skill/traits
        self.assertEqual(result[0x3ffa1:0x3ffb6], bytes.fromhex('2097bdbfafbd875cdebd872097bdad8b0e5cf6bd87'))
