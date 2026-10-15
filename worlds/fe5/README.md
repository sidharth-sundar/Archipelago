# Thracia AP world scaffold

Not playable. The package deliberately does not register a World or client yet.
No generation, ROM hooks or delivery behavior is implemented by these stubs.

This follows Sacred Stones' repository split and lower-case world module layout:

```text
thracia_ap/
  FireEmblem5/             # ROM source, build tools, design/audits, emulator testing
  Archipelago/            # fork of ArchipelagoMW/Archipelago
    worlds/fe5/
      __init__.py         # future World registration and generation lifecycle
      archipelago.json    # source manifest
      constants.py
      items.py
      locations.py
      options.py
      rom.py              # seed patch production/application
      client.py           # SNES SNI handler (FE8 uses a GBA client instead)
      connector_config.py # generated shared IDs and final symbol addresses
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

## Packaging when implementation is ready

Use upstream's Build APWorlds component rather than maintaining a separate ZIP
builder. From the Archipelago repository root, after installing its Python
dependencies and implementing/validating World registration:

```powershell
python Launcher.py "Build APWorlds" -- "Fire Emblem: Thracia 776" --skip_open_folder
```

Expected output: `build/apworlds/fe5.apworld`, containing `fe5/__init__.py`,
`fe5/archipelago.json`, client/world modules and distributable runtime data.
The upstream builder supplies container-version metadata. Select the minimum
supported AP version after compatibility testing; it is not claimed yet.

**This command cannot build a functional Thracia world at the scaffold stage.**
Do not publish an empty archive as a release. Register the world and SNI handler,
implement generation and patch output, and meet the testing acceptance gates first.

The `.apworld` is the reusable integration installed by users and the generator.
The generated per-player patch is a separate artifact, applied locally to the
verified LM ROM. Neither artifact includes a complete ROM or personal save.

Release verification must install the built archive in a clean AP environment,
without the loose `worlds/fe5` folder, then test discovery, generation, patching,
client discovery and an end-to-end send/receive. Confirm archive contents exclude
ROMs, fixtures, caches and development tests. Check packaged resource loading;
do not assume resources are ordinary files outside a ZIP.
