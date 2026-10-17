# Thracia Chapter 1 development build

This is a development build, not an accepted v0 release. See the ROM repository's
`docs/chapter1-implementation.md` for the current acceptance record. Do not use
an important multiworld session to test it.

## Files and versions

- `fe5.apworld`: install through Archipelago Launcher → Install APWorld, then restart.
- `Thracia.yaml`: default player configuration; rename the player if desired.
- `FE5Patcher.exe`: reusable Windows patcher, with command-line and file-dialog modes.
- `exlorom-sni.lua`: generic transport adapter, used with SNI's unmodified `Connector.lua`.
- Your own unmodified, unheadered Lil' Manster 1.08 `.sfc`, 6,291,456 bytes,
  SHA-1 `7db4211d827c26d3ae938c6bb383d9427beedb75`.

Development checks use Archipelago 0.6.9 source, Python 3.12.14, BizHawk 2.11.1
with **BSNESv115+**, and SNI 0.0.103. The older **BSNES** core maps the expanded ROM
differently and is not supported. Snes9x is not the tested core.

## Generate, patch and connect

1. Install the APWorld. Put the default YAML in the generator's Players directory.
   Generate normally; share the server's `.archipelago` file with the host.
2. Extract your `.apfe5` from the generated ZIP. Double-click `FE5Patcher.exe` and
   select the base LM ROM, the `.apfe5`, and a new output `.sfc` path. Alternatively:

   ```powershell
   .\FE5Patcher.exe --base "Lil' Manster 1.08.sfc" --patch player.apfe5 --output player.sfc
   ```

   The patcher verifies the base hash, protocol, hook bytes and allocation. It
   writes atomically and refuses to overwrite the source ROM. The `.apfe5` has
   no complete ROM; generation does not need a ROM.
3. Start SNI. Open the patched ROM in BizHawk using BSNESv115+.
4. Put `exlorom-sni.lua` beside SNI's `lua/Connector.lua` and `lua/x64` directory.
   Open **exlorom-sni.lua** in BizHawk's Lua Console. Keep the files together: the
   upstream connector locates its socket library relative to that directory.
   The adapter supplies missing ExLoROM CARTRAM access through System Bus; it
   contains no Thracia check, inventory or receipt logic.
5. Launch Archipelago's **SNI Client** and connect to the room. The ROM identifies
   the player slot; do not use a patch from another seed. SNI's local address is
   `localhost:23074`.
6. Start a fresh game. Do not import LM saves or external savestates. Check the
   SNI Client log for identity or SRAM errors before playing.
7. After saving or suspending in-game, use **File → Save RAM → Flush Save Ram**
   (`Ctrl+S`) before closing BizHawk. Keep backups of that seed's `.SaveRAM` file.
   Explicit flushing is required for the tested workflow; closing the window
   alone did not reliably write SRAM during testing. See
   [BizHawk's save instructions](https://github.com/TASEmulators/BizHawk#in-game-saves).

## Chapter 1 behavior

The five successful house visits send checks. Osian and Halvan still must visit
their own houses. Dialogue and house closure remain; original rewards are
suppressed. The pool is one each of Vouge, Brave Axe, Vulnerary, Iron Sword and
Life Ring, and uses normal multiworld placement.

Incoming items wait until a player-phase boundary and enter Leif's free slots
with normal durability. A full inventory defers delivery; free a slot and wait
until the next player phase. There is no eviction, spillover or convoy delivery.
Each delivered item shows the native item-received popup. Several queued rewards
appear one at a time before map control returns for that player phase.
The two queues each have 16 entries. v0 retains the arrival history for the
whole seed (only five rewards normally arrive), and stops instead of wrapping.

Seizing reports victory plus every missed house directly, displays the Chapter 1
completion dialogue, and stops chapter advancement. Dismissing the dialogue
leaves the completed map frozen; the SNI client remains connected.

Offline checks are stored in SRAM. Native saves have companion receipt state;
loading restores the inventory's receipt position while retaining the global
arrival history. Native save-copy/deletion and 32 cold-boot recovery cases have
passed focused emulator tests, including interruptions during rollback. The full
Chapter 1 playthrough remains an acceptance gate; see the ROM repository's record.
BizHawk must also flush its save RAM to disk; the ROM cannot make an emulator
process crash or an arbitrary external savestate import transactional.

## Focused debugging

Use only disposable local rooms. The ROM repository supplies fixture identity
recording/verification and an optional developer input controller. Start from
normal new-game initialization and keep the post-opening baseline unchanged.
Fixture metadata binds the ROM hash, core/version, seed identity and state hash.
Record any fixture-only unit placement or defeated-enemy setup; that is not
evidence of tactical solvability or a full manual clear.
