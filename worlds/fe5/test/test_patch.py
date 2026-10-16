import copy
import hashlib
from importlib.resources import files
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from ..definitions import ITEMS, LOCATIONS
from ..patchcore import BASE_SHA1, apply_patch, patch_file
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

    def test_generated_queue_addresses_are_complete(self):
        from .. import connector_config as config
        runtime = json.loads(files("worlds.fe5").joinpath("data/runtime.json").read_bytes())
        # 64tass prints arithmetic aliases in decimal; these must survive export.
        for name in ("AP_PROCESSED", "AP_DELIVERED", "AP_SAVED", "AP_PENDING"):
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
        self.seed = {"protocol": 1, "identity": "00112233445566778899aabbccddeeff", "slot": 1}

    def test_real_patch_and_source_unchanged(self):
        result = apply_patch(self.base, self.runtime, self.seed)
        self.assertEqual(len(result), len(self.base))
        self.assertEqual(result[0x4a0000:0x4a0008], b"FE5AP001")
        self.assertEqual(result[0x7fd8], 7)
        self.assertEqual(result[0x407fd8], 7)
        self.assertEqual(hashlib.sha1(self.base_path.read_bytes()).hexdigest(), BASE_SHA1)

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
