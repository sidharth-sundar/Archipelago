# Thracia Chapters 1–2x development build

This is a development build, not an accepted v0 release. See the ROM repository's
`docs/chapter2x.md` for the current implementation and verification workflow. Do not use
an important multiworld session to test it.

## Files and versions

- `fe5.apworld`: install through Archipelago Launcher â†’ Install APWorld, then restart.
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
7. After saving or suspending in-game, use **File â†’ Save RAM â†’ Flush Save Ram**
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
The immutable arrival history holds 1,024 receipts; the pending FIFO ring holds
16 at a time and reuses freed entries. A per-save bitmap records which receipt
indexes have been applied. History stops instead of overwriting when full. Nothing is
silent filler: it consumes a receipt entry but no inventory space or popup.

Recruitment, village, conversation and completion toggles apply across Chapters
1, 2 and 2x. `ground_pickup` controls the two Chapter 2x Torch tiles and adds
two Torches to the pool. Disabled categories retain native rewards and behavior.
Characters and their recruitment inventories never become AP rewards.

`shopsanity` adds the vendors in Chapters 1 and 2. The first purchase sends a
check; later purchases give ordinary Vulneraries. Stock contribution and price
options retain their existing behavior, including Bargain and unchanged selling.

`capturesanity_easy` adds Lifis's AP Check token; `capturesanity_hard` adds
Shiva's. Both are in Chapter 2x. Obtain them by ordinary capture/trade, Steal or
Thief staff. A living player holder must finish acting before redemption. An
already-grayed recipient redeems after the trade closes. Canto and immediate
movement-star refresh must settle first. Convoy/enemy-held tokens do not redeem.
Tokens cannot be used, equipped, sold or discarded; duplicate collected tokens
are removed at the same eligible boundary without another check.

All categories, shops and capture tiers yield 31 locations and eleven base
physical rewards. Extras replace the twenty remaining filler slots. Guaranteed
pool overflow fails generation. All check categories off remains valid.

Protocol 9 / APWorld 0.0.9 requires fresh patches and saves. Chapters 1 and 2 run
their native endings without releasing missed checks. Native Chapter 2 gaiden
prerequisites are unchanged: destroying any of the three savable villages skips
2x. A skip finishes after Chapter 2's ending. Otherwise, victory follows Chapter
2x's ending recruitment and roster cleanup. Either route reports all remaining
enabled locations and stops before Chapter 3; SNI keeps polling.

`fix_ambush_spawns` moves only the enumerated native Chapter 2/2x reinforcement
waves to player phase of the same numbered turn. It retains probabilities,
blocking and boss conditions. AP reinforcements always use player-phase timing.

Pending physical rewards and effects carry between chapters. Temporary fog,
music and movement modifiers clear before leaving the old map. At most one
queued effect activates per player phase, including Chapter 2's first phase.
Collect and drain desired effects before the final seizure.

Offline checks are stored in SRAM. Native saves have companion receipt state;
loading restores the inventory's receipt position while retaining the global
arrival history. Native save-copy/deletion and interrupted saves pair the applied
bitmap with inventory. See the ROM repository's current acceptance evidence;
the protocol-2 staged game was successfully playtested by the user.
BizHawk must also flush its save RAM to disk; the ROM cannot make an emulator
process crash or an arbitrary external savestate import transactional.

## Focused debugging

Use only disposable local rooms. The ROM repository supplies fixture identity
recording/verification and an optional developer input controller. Start from
normal new-game initialization and keep the post-opening baseline unchanged.
Fixture metadata binds the ROM hash, core/version, seed identity and state hash.
Record any fixture-only unit placement or defeated-enemy setup; that is not
evidence of tactical solvability or a full manual clear.


## Extra valuable rewards (0.0.4)

Set `enable_extra_valuable_items: true` to add guaranteed rewards. The default
YAML lists nine booster counts (0â€“9 each), random booster mode and count (0â€“9),
a Boots exclusion toggle, and Warp/Rescue counts (0â€“3 each). All default to zero
or false. Random mode ignores individual booster counts and draws uniformly
with replacement; staff counts remain independent. Boots is named Leg Ring in
the native LM menus. Counts are additional to vanilla village/shop pool entries.

Generation fails with player/count details if configured rewards exceed enabled
locations. Remaining slots contain Nothing. New rewards are useful, not required
for Chapter 1 victory. Delivery uses the existing FIFO and prompts; free inventory
space and wait for a player phase. Warp/Rescue keep native rank restrictions and
have no normal user in Chapter 1. No staff access or character changes are added.

Protocol 4 requires fresh patches and saves. Do not replace a protocol-3 ROM in
an existing session. Configuration and resolved random counts are verified
against the ROM before the client sends or receives. Existing saves/playthroughs
should be kept in separate directories.

## Custom consumables (protocol 5)

`extra_arms_scrolls` and `extra_critical_manuals` each accept 0-9 (default 0),
under `enable_extra_valuable_items`. They replace Nothing; overflow is an error.
Random booster mode does not override these counts. Fresh patches/saves are required.

Arms Scroll adds up to 50 personal WEXP, respecting the effective A cap. It uses
an equipped weapon first; otherwise a usable staff. To target staves, remove
weapons and retain an eligible staff. An equipped weapon at A blocks use.
Critical Manual adds one FCM to the character, up to five. Each item has one use.
Native save/load/copy/delete preserves the character bonus and consumed item together.
Staff Manual remains deferred.


## Traps and beneficial effects (protocol 6)

Use fresh protocol-9 patches and saves; earlier builds are incompatible.
`filler_effect_chance` (0â€“100, default 0) replaces remaining Nothing slots with
weighted effects. `boss_music_weight`, `heal_players_weight`,
`heal_enemies_weight`, `fog_weight`, and `movement_one_weight` are relative
weights from 0 to 100, default 1. Zero disables an effect; all zero leaves Nothing.
Guaranteed physical rewards still take priority and overflow still fails generation.

One effect activates at each player-phase start independently of inventory space.
Music, fog, and movement caps last until the next player phase. Effects show a
native message; they never occupy inventory slots. Fog retains torch vision,
and the movement cap leaves Boots and movement growths intact.

Effect receipts are consumed seed-globally before activation, so an older native
save does not trigger them again. A suspend made while an effect is active
resumes its saved remaining duration. A precisely timed reset may lose a trap
activation; arbitrary savestates and emulator-process crashes have no delivery
guarantee. Physical items retain their existing native-save replay behavior.
Effects queued after completion wait because the victory screen has no player phase.


Protocol-6 validation used Archipelago 0.6.9, BizHawk 2.11.1 / BSNESv115+ and
SNI 0.0.103. Use the included ExLoROM Lua adapter. Effects are consumed globally
for this seed and slot; a native load can replay an unsaved physical item but
cannot replay an already-consumed effect. A copied active suspend retains its
modifier and remaining turn duration.

## Reinforcement and rotation effects

APWorld 0.0.9 requires fresh protocol-9 patches and saves. Set
`filler_effect_chance` above zero to replace Nothing with weighted effects.
The five new weights are `dancer_reinforcements_weight`,
`ballista_reinforcements_weight`, `siege_reinforcements_weight`,
`rotate_players_weight`, and `rotate_enemies_weight` (0–100, default 1).
Set any weight to zero to exclude it. Existing effect weights still participate.

Dancers, ballistae and siege sorcerers appear near the current chapter seize point,
without occupying it. Their equipment cannot be captured or stolen. Rotations
move eligible units among their existing legal tiles; enemies exclude the boss
and stationary units. Effects activate once per player phase, independently
of Leif's inventory. Spawned units and rotations persist normally; loading an
older native save does not reapply a consumed trap. Guaranteed rewards and
location counts are unchanged. Production support covers Chapters 1, 2 and 2x.

## Chapter 2 debug start

Set `debug_start_chapter: 2` for a separate fresh debug file. It bootstraps all
eight Chapter 1 allies with native inventories, full HP and zero native gold.
Ronan remains unrecruited. Prior enabled checks report normally, delivering
their actual multiworld rewards. `debug_exp_per_chapter: 70` gives 70 EXP for
the skipped chapter without leveling. Range: 0–1000. `debug_growth_mode` accepts
`fixed` or `random`; growth RNG is reproducible and independent of combat RNG.
Native caps apply, with no automatic promotion or WEXP. Bootstrap runs only
on fresh-file initialization, not on save/load/copy/resume.

## Chapter 2x debug start and protection indicator

`debug_start_chapter: 2x` bootstraps all nine earlier recruits, including Ronan,
with native inventories and the normal Chapter 2x opening. At the default EXP
setting they receive 140 EXP (one gained level, 40 EXP). Lifis and Safy remain
unrecruited. Earlier enabled checks retain real placements and report through
the client; their receipts can fill Leif's inventory before the Boots arrive.
Trade items away and advance a player phase to receive pending physical rewards.

Fog on naturally foggy Chapter 2x is a notified no-op. It consumes the effect
without touching native fog, torch bonuses or later restoration state.

Protected AP reinforcements show a display-only **Archipelago+** skill, using the
Steal icon, only under information setting **3: Hidden Skills**. This does not
grant Steal or replace ordinary Steal/Miracle+. Its help text explains capture
and equipment-theft protection.
