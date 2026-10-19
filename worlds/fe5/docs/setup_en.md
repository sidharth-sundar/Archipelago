# Thracia Chapters 1–4 development build

Protocol **11 / APWorld 0.0.11** requires fresh patches and saves. Keep older
playthroughs in their original directories. This development build ends after
Chapter 4's native ending, before Chapter 4x or Chapter 5 initialization.

## Install, generate, patch, connect

1. Install `fe5.apworld` through Archipelago Launcher's Install APWorld component
   and restart the launcher. Put `Thracia.yaml` in the generator's Players folder.
2. Generate a multiworld. Give the host its `.archipelago` file and extract your
   `.apfe5` patch from the output ZIP.
3. Run `FE5Patcher.exe` and select the patch, your unmodified Lil' Manster 1.08
   `.sfc`, and a new output path. The input must be unheadered, 6,291,456 bytes,
   SHA-1 `7db4211d827c26d3ae938c6bb383d9427beedb75`.

   ```powershell
   .\FE5Patcher.exe --base "Lil' Manster 1.08.sfc" --patch player.apfe5 --output player.sfc
   ```

   The patcher verifies the base, protocol, original hook bytes and allocations;
   it writes atomically without modifying the input. Generation needs no ROM.
4. Start SNI. Open the patched ROM in BizHawk using **BSNESv115+**. Put the
   supplied `exlorom-sni.lua` beside SNI's `Connector.lua` and `x64` dependencies,
   then run it through BizHawk's Lua Console. The older BSNES core is unsupported.
5. Open Archipelago's SNI Client and connect to the room. The patch identifies
   its slot automatically. SNI's default WebSocket address is `localhost:23074`.
6. Begin a fresh file, or use only the explicitly supplied native save for that
   exact validation seed. Existing LM saves and arbitrary savestates are unsupported.
7. Save/suspend in-game, then flush Save RAM (`Ctrl+S`) before closing BizHawk.
   Keep backups of that seed's `.SaveRAM` file.

Resume with the same BizHawk configuration and SaveRAM directory. Double-clicking
a ROM may launch a different emulator installation through the Windows file
association; an empty file menu there does not mean the original save was deleted.

Development uses Archipelago 0.6.9, Python 3.12.14, BizHawk 2.11.1 / BSNESv115+,
and SNI 0.0.103. See the ROM repository's `docs/chapter4.md` for evidence and
remaining manual coverage. Packaging alone does not certify emulator acceptance.

## Checks and completion

The existing recruitment, village, conversation, completion, ground-pickup,
chest, shop and capture-tier options retain their meanings across supported maps.
Disabled checks do not report, including at final cleanup. Village predicates,
matching-child returns, recruitment prerequisites and gaiden access remain native.
Characters and confiscated belongings never become AP reward-pool contributions.

Chapter 4 adds six recruits, one shared Leif/Lifis-to-Dalsin Talk, four fixed chest
tokens, six civilian escapes, five blue escape milestones, and Leif's escape.
`blue_escapesanity` and `green_escapesanity` default on. Blue checks count the first
five distinct non-Leif player characters, not specific names. Player passengers
count separately from carriers; civilian passengers count toward their own green
checks. Enemy prisoners do not count. Native civilian flags still govern 4x.

With every category and shop contribution on: **63 locations and 21 physical
rewards**, before extras. The default YAML has 57 locations and 17 physical rewards.
Configured extras replace filler; guaranteed rewards exceeding locations fail
before patch output. No new placement or tactical-solvability restrictions apply.
Only Chapter 4 completion releases all remaining enabled checks and reports victory.
Earlier maps transition normally without releasing missed checks.

Chest and capture tokens are tradable location identifiers. A living player
holder redeems them after finishing an action, after canto/movement-star handling.
Enemy-held, convoy-held and recovery-chest tokens stay unredeemed. Already-collected
duplicates disappear without another send. Tokens cannot be used, equipped, sold,
or discarded. Purchased shop checks revert to unlimited native stock afterward.

## Receipts and the Chapter 4 prison opening

The immutable history holds **1,024 receipts**, with separate reusable 16-entry
physical and effect queues. Native saves pair inventory/convoy state with applied
receipt bits. Older native saves can replay physical rewards; consumed effects do
not run again. Duplicate packets do not grant duplicate saved rewards. Arbitrary
savestates and emulator-process crashes remain outside these guarantees.

Chapter 4 captures a fixed accepted-receipt boundary during its opening. Four
fixed chests are reserved, then twelve recovery slots are filled by native item
priority while Leif is refilled from the bounded FIFO. Original durability is
preserved. A seed-derived permutation places the occupied chests.

Remaining prisoner property and bounded physical rewards go to the convoy. The
final transfers and their messages run at the first visible player-phase boundary,
before player control, effects or ordinary delivery; skipping opening dialogue is
safe. Both prisoners are empty when control begins. Effects remain queued.

While Leif's cell door at **(7,24)** is closed, new physical receipts go to the
convoy. Opening it resumes ordinary Leif delivery on subsequent player phases.
Already-stored convoy items stay there. A full Leif inventory defers delivery.
The full convoy never causes equipment to be returned to locked-cell Leif.

Every new send displays `Sent AP item.` Physical inventory receipts retain native
item popups; diverted items name their convoy destination. Replacements/discards
are identified accurately. Nothing has no gameplay effect and retains the existing
`Received AP item: Nothing` acknowledgement. Effects use their own named notices.

## Expanded convoy

The convoy has **512 continuous slots**, including native take/give, sorting,
scrolling and party-item searches. Its contents, escaped-character bookkeeping,
and protected recovery storage belong to the native-save companion. The original
32 KiB native save layout is preserved inside expanded 128 KiB SRAM.

At capacity, ordinary incoming items replace the lowest-priority eligible item
only if their native priority is higher; existing items win ties. AP tokens,
Arms Scrolls, Critical Manuals and native unsellable/personal weapons are never
automatically evicted. Protected receipts remain pending when no eligible storage
exists. Already-confiscated protected property has bounded saved recovery storage.
Generation emits an advisory capacity report at 154 physical contributions; this
is an audit threshold, not a generation restriction.

## Extras and effects

`enable_extra_valuable_items` gates additional boosters, Warp/Rescue, Arms Scrolls
and Critical Manuals. Manual counts and seeded random-booster mode retain their
existing behavior. Arms Scroll gives up to 50 personal WEXP to an equipped weapon,
otherwise an eligible staff; remove weapons to target staff rank. Critical Manual
adds one FCM, capped at five. Staff Manual remains deferred.

`filler_effect_chance` replaces only remaining filler by seeded weighted effects.
One effect runs per eligible player phase regardless of inventory space. Temporary
music, fog and movement caps expire next player phase and clear between maps.
Natural fog makes Fog a notified no-op. AP reinforcements remain protected from
capture/theft and show Archipelago+ only with Hidden Skills information enabled.
Rotations preserve terrain legality. Chapter 4 reinforcements reserve both northern
escape tiles. `fix_ambush_spawns` moves only the audited waves, with detection
evaluated before Chapter 4's moved soldier arrivals.

## Debug starts and the Chapter 4 validation file

`debug_start_chapter` accepts `1`, `2`, `2x`, `3`, or `4`. Earlier recruits receive
`debug_exp_per_chapter` per skipped map using fixed or seeded-random growths,
native caps, no automatic promotions and no automatic WEXP. Bootstrap runs once.
Chapter 4 supplies the eleven earlier recruits with native prison-arc availability,
includes Lifis and sets Jubel's prerequisite; the native opening creates new allies.
The default four skipped maps give 280 EXP. Earlier enabled checks report normally,
except Lifis's unredeemed AP token remains uncollected.

`chapter4-validation.yaml`, generated with seed **2026101904** and item plando,
produces the requested 23 physical rewards and 40 Nothing entries. The separate
fourteen-item inventory fixture is developer-only and is not part of normal
world generation. The supplied native pre-opening save and session evidence document
it separately from the nine real AP physical receipts. See `docs/chapter4.md` in
the ROM repository for exact priority selection, permutation and acceptance results.

Future balancing: audit guaranteed thief/lockpick access before widening logic.
This milestone does not change starting lockpicks or impose placement guarantees.
