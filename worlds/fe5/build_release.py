"""Developer-only reproducible packaging via upstream's Build APWorlds component.

Run from the Archipelago root with: python worlds/fe5/build_release.py --output DIR
Build the ROM payload in FireEmblem5 first. This does not certify manual acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    world = root / "worlds/fe5"
    os.chdir(root)
    sys.path.insert(0, str(root))
    import unittest  # use upstream's world scoping for this developer-only build
    os.environ["AP_TEST_WORLDS"] = "fe5"
    from worlds.LauncherComponents import _build_apworlds
    _build_apworlds("Fire Emblem: Thracia 776", "--skip_open_folder")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "build/apworlds/fe5.apworld", output / "fe5.apworld")
    shutil.copyfile(world / "default.yaml", output / "Thracia.yaml")
    shutil.copyfile(world / "docs/setup_en.md", output / "SETUP.md")
    for name in ("chapter2x-validation.yaml", "chapter2x-debug.yaml"):
        shutil.copyfile(world / "docs" / name, output / name)
    adapter = root.parent / "FireEmblem5/ap/emulator/exlorom-sni.lua"
    if not adapter.is_file():
        raise FileNotFoundError("Build beside the FireEmblem5 repository to include the SNI adapter")
    shutil.copyfile(adapter, output / adapter.name)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--name", "FE5Patcher",
                    "--distpath", str(output), "--workpath", str(output / "build"),
                    "--specpath", str(output / "build"), "--paths", str(world), str(world / "patcher.py")], check=True)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()
              if p.is_file() and p.name != "SHA256SUMS.json"}
    (output / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2) + "\n")


if __name__ == "__main__":
    main()
