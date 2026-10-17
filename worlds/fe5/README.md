# Thracia AP Chapter 1 implementation

The package registers up to sixteen optional Chapter 1 locations, an SNI handler, and generates
`.apfe5` patches. The Python tests, installed-archive generation and focused
emulator checks are being validated. This is a development build, not an accepted
v0 release. Follow [setup](docs/setup_en.md) and the current acceptance record in
`FireEmblem5/docs/chapter1-checks.md`. Four default-on YAML toggles control
recruitment, village, conversation and completion checks. Protocol 2 requires
fresh generated patches and saves. Nothing is silent filler; no additional
physical reward types are introduced.

This follows Sacred Stones' repository split and lower-case world module layout:

```text
thracia_ap/
  FireEmblem5/             # ROM source, build tools, design/audits, emulator testing
  Archipelago/            # fork of ArchipelagoMW/Archipelago
    worlds/fe5/
      __init__.py         # World registration and generation lifecycle
      archipelago.json    # source manifest
      constants.py
      items.py
      locations.py
      options.py
      rom.py              # seed patch production/application
      client.py           # SNES SNI handler (FE8 uses a GBA client instead)
      definitions.py      # generated item/location IDs and wire constants
      connector_config.py # generated final symbol addresses
      data/               # distributable patch and generated runtime tables
      docs/               # player setup guide
      test/               # Python world/protocol/patch tests
```

The separate ROM project remains in its existing build layout: copying FE8's
GBA-specific build directories or assembler would not help the SNES build.
Reference clones elsewhere in the workspace are research inputs, not dependencies.

Canonical planning documents remain in the sibling ROM repository:
[design](../../../FireEmblem5/docs/archipelago-design.md),
[tests](../../../FireEmblem5/docs/testing-workflow.md), and
[chapter debug fixtures](../../../FireEmblem5/docs/chapter-debug-workflow.md).
These relative links are for the local sibling checkout layout.

## Build development artifacts

Use upstream's Build APWorlds component rather than maintaining a separate ZIP
builder. From the Archipelago repository root, after installing its Python
dependencies and building the ROM runtime:

```powershell
python Launcher.py "Build APWorlds" -- "Fire Emblem: Thracia 776" --skip_open_folder
```

Expected output: `build/apworlds/fe5.apworld`, containing `fe5/__init__.py`,
`fe5/archipelago.json`, client/world modules and distributable runtime data.
The upstream builder supplies container-version metadata. Select the minimum
supported AP version after compatibility testing; it is not claimed yet.

The command now builds the implemented integration. The ROM runtime must first
be rebuilt from `FireEmblem5/ap/runtime.asm` using the exact supported base.
`build_release.py` also compiles the reusable Windows patcher and stages player
instructions/YAML. Passing packaging alone does not satisfy manual acceptance.

The `.apworld` is the reusable integration installed by users and the generator.
The generated per-player patch is a separate artifact, applied locally to the
verified LM ROM. Neither artifact includes a complete ROM or personal save.

Release verification must install the built archive in a clean AP environment,
without the loose `worlds/fe5` folder, then test discovery, generation, patching,
client discovery and an end-to-end send/receive. Confirm archive contents exclude
ROMs, fixtures, caches and development tests. Check packaged resource loading;
do not assume resources are ordinary files outside a ZIP.
