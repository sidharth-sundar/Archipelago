"""Standalone patch procedure used by both AP and the Windows patcher.

Only the standard library is required. A seed patch is data, never executable
Python. No bundled ROM, filesystem extraction, shelling out, or eval.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

BASE_SHA1 = "7db4211d827c26d3ae938c6bb383d9427beedb75"
GAME = "Fire Emblem: Thracia 776"
PROTOCOL = 7

try:
    from .extra_items import extra_config_bytes
    from .effects import effect_config_bytes
except ImportError:  # Standalone Windows patcher
    from extra_items import extra_config_bytes
    from effects import effect_config_bytes


def shop_config_bytes(config):
    """Canonical ROM configuration: two tenths multipliers and four toggle bits."""
    names = ("armorysanity", "shopsanity", "armory_items_in_pool", "shop_items_in_pool")
    if not isinstance(config, dict) or set(config) != set(names) | {"armory_price_multiplier", "shop_price_multiplier"}:
        raise ValueError("Invalid shop configuration")
    if any(type(config[n]) is not int or config[n] not in (0, 1) for n in names):
        raise ValueError("Invalid shop toggle")
    prices = [config[n + "_price_multiplier"] for n in ("armory", "shop")]
    if any(type(p) is not int or not 1 <= p <= 100 for p in prices):
        raise ValueError("Invalid price multiplier")
    flags = sum(config[name] << bit for bit, name in enumerate(names))
    return b"".join(p.to_bytes(2, "little") for p in prices + [flags])


def purchase_price(base_price, tenths, bargain=False):
    if type(tenths) is not int or not 1 <= tenths <= 100 or base_price < 0:
        raise ValueError("Invalid purchase price")
    price = base_price * tenths // 10
    if price > 65535:
        raise ValueError("Scaled price exceeds native shop price field")
    return price // 2 if bargain else price


def valid_mask(mask):
    return (type(mask) is int and 0 <= mask <= 0x1ffff
            and all(mask & group in (0, group) for group in (0x1f, 0x1fe0, 0x6000, 0x8000, 0x10000)))


def apply_patch(base: bytes, runtime: dict, seed: dict) -> bytes:
    if len(base) != 0x600000 or hashlib.sha1(base).hexdigest() != BASE_SHA1:
        raise ValueError("Base must be the unmodified, unheadered Lil' Manster 1.08 .sfc (SHA-1 7db4211d...).")
    if runtime["base_sha1"] != BASE_SHA1 or runtime["protocol"] != PROTOCOL or seed["protocol"] != PROTOCOL:
        raise ValueError("Incompatible FE5 patch protocol or base")
    identity = bytes.fromhex(seed["identity"])
    enabled_mask = seed.get("enabled_mask")
    config = shop_config_bytes(seed.get("shop_config"))
    extra_hash = extra_config_bytes(seed.get("extra_items"))
    effect_hash = effect_config_bytes(seed.get("effects"))
    if not valid_mask(enabled_mask):
        raise ValueError("Invalid enabled-location mask")
    if bool(enabled_mask & 0x10000) != bool(seed["shop_config"]["shopsanity"]):
        raise ValueError("Shop configuration does not match enabled locations")
    if len(identity) != 16 or not 1 <= seed["slot"] <= 65535:
        raise ValueError("Invalid seed/slot identity")
    out = bytearray(base)
    occupied = []
    allocation = runtime["allocation"]
    if allocation != {"file_start": 0x4a0000, "file_end": 0x4b0000, "cpu_start": 0x148000}:
        raise ValueError("Unknown ROM allocation")
    if any(base[allocation["file_start"]:allocation["file_end"]]):
        raise ValueError("Reserved ROM allocation is occupied")
    for change in runtime["writes"]:
        start = change["offset"]
        data = bytes.fromhex(change["data"])
        end = start + len(data)
        if not 0 <= start < end <= len(base):
            raise ValueError("Patch write outside ROM bounds")
        if any(start < other_end and other_start < end for other_start, other_end in occupied):
            raise ValueError("Overlapping patch writes")
        occupied.append((start, end))
        if "zero_length" in change:
            if start != allocation["file_start"] or end > allocation["file_end"] or change["zero_length"] != len(data):
                raise ValueError("Runtime exceeds allocation")
            expected = bytes(len(data))
            if hashlib.sha256(data).hexdigest() != runtime["runtime_sha256"]:
                raise ValueError("Corrupt runtime payload")
        else:
            expected = bytes.fromhex(change["expected"])
        if len(expected) != len(data) or base[start:end] != expected:
            raise ValueError(f"Original-byte assertion failed at {start:#x}")
        if not change.get("enabled_bits") or enabled_mask & change["enabled_bits"]:
            out[start:end] = data
    header = allocation["file_start"]
    if out[header:header + 8] != b"FE5AP007":
        raise ValueError("Missing AP runtime header")
    out[header + 8:header + 24] = identity
    out[header + 26:header + 28] = seed["slot"].to_bytes(2, "little")
    out[header + 28:header + 32] = enabled_mask.to_bytes(4, "little")
    out[header + 32:header + 38] = config
    out[header + 38:header + 54] = extra_hash
    out[header + 54:header + 70] = effect_hash
    # SNES checksum for 6 MiB mirrored into an 8 MiB address span.
    for h in (0x7fc0, 0x407fc0):
        out[h + 0x1c:h + 0x20] = b"\xff\xff\0\0"
    checksum = (sum(out[:0x400000]) + 2 * sum(out[0x400000:])) & 0xffff
    for h in (0x7fc0, 0x407fc0):
        out[h + 0x1c:h + 0x20] = (checksum ^ 0xffff).to_bytes(2, "little") + checksum.to_bytes(2, "little")
    return bytes(out)


def patch_file(base_path, patch_path, output_path):
    base_path, patch_path, output_path = map(Path, (base_path, patch_path, output_path))
    if output_path.resolve() in (base_path.resolve(), patch_path.resolve()):
        raise ValueError("Output must differ from the base ROM and seed patch")
    with zipfile.ZipFile(patch_path) as archive:
        required = ("archipelago.json", "seed.json", "runtime.json")
        if any(archive.namelist().count(name) != 1 for name in required):
            raise ValueError("Invalid or ambiguous .apfe5 patch")
        if any(archive.getinfo(name).file_size > 2_000_000 for name in required):
            raise ValueError("Oversized patch metadata")
        manifest, seed, runtime = (json.loads(archive.read(name)) for name in required)
    if manifest.get("game") != GAME or manifest.get("player") != seed["slot"]:
        raise ValueError("Patch manifest does not match seed slot")
    result = apply_patch(base_path.read_bytes(), runtime, seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=output_path.parent, prefix=".fe5-", delete=False) as handle:
            temp = Path(handle.name)
            handle.write(result)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, output_path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return output_path
