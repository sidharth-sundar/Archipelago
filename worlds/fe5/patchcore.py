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
PROTOCOL = 1


def apply_patch(base: bytes, runtime: dict, seed: dict) -> bytes:
    if len(base) != 0x600000 or hashlib.sha1(base).hexdigest() != BASE_SHA1:
        raise ValueError("Base must be the unmodified, unheadered Lil' Manster 1.08 .sfc (SHA-1 7db4211d...).")
    if runtime["base_sha1"] != BASE_SHA1 or runtime["protocol"] != PROTOCOL or seed["protocol"] != PROTOCOL:
        raise ValueError("Incompatible FE5 patch protocol or base")
    identity = bytes.fromhex(seed["identity"])
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
        out[start:end] = data
    header = allocation["file_start"]
    if out[header:header + 8] != b"FE5AP001":
        raise ValueError("Missing AP runtime header")
    out[header + 8:header + 24] = identity
    out[header + 26:header + 28] = seed["slot"].to_bytes(2, "little")
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
