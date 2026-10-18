"""Thracia handler for the standard BizHawk/SNI transport."""
import logging
import struct
from NetUtils import ClientStatus
from worlds.AutoSNIClient import SNIClient
from .constants import GAME_NAME
from .connector_config import (ROM_HEADER, HEADER_SIZE, AP_MAGIC, AP_ARRIVALS)
from .definitions import PROTOCOL, HISTORY_CAPACITY
from .protocol import ENTRY_SIZE, ProtocolError, accepted_count, checks_for, encode_receipt
from .patchcore import valid_mask, shop_config_bytes
from .extra_items import extra_config_bytes
from .effects import effect_config_bytes
from .debug import debug_config_bytes

logger = logging.getLogger("SNES")


class FE5SNIClient(SNIClient):
    game = GAME_NAME
    patch_suffix = ".apfe5"

    async def validate_rom(self, ctx):
        from SNIClient import snes_read
        header = await snes_read(ctx, ROM_HEADER, HEADER_SIZE)
        if not header or len(header) != HEADER_SIZE or header[:8] != b"FE5AP008":
            return False
        if int.from_bytes(header[24:26], "little") != PROTOCOL:
            logger.error("FE5 ROM/client protocol mismatch")
            return False
        identity = header[8:24]
        if not any(identity):
            return False
        if not valid_mask(int.from_bytes(header[28:32], "little")):
            return False
        ctx.game = self.game
        ctx.items_handling = 0b111  # server sends own-world, remote and start items
        if getattr(ctx, "rom", None) != identity:
            ctx.fe5_error = None
        ctx.rom = identity
        ctx.fe5_slot = int.from_bytes(header[26:28], "little")
        return True

    async def game_watcher(self, ctx):
        from SNIClient import snes_read, snes_buffered_write, snes_flush_writes
        if ctx.server is None or ctx.slot is None:
            return
        # Never use mutable handler instance fields: AutoSNI registers a singleton.
        header = await snes_read(ctx, ROM_HEADER, HEADER_SIZE)
        if (not header or len(header) != HEADER_SIZE or header[:8] != b"FE5AP008" or header[8:24] != ctx.rom
                or int.from_bytes(header[24:26], "little") != PROTOCOL
                or int.from_bytes(header[26:28], "little") != ctx.slot):
            return
        slot_data = getattr(ctx, "fe5_slot_data", {}) or {}
        enabled_mask = int.from_bytes(header[28:32], "little")
        try:
            config = shop_config_bytes(slot_data.get("shop_config"))
            extra_hash = extra_config_bytes(slot_data.get("extra_items"))
            effect_hash = effect_config_bytes(slot_data.get("effects"))
            debug = debug_config_bytes(slot_data.get("debug_config"))
        except ValueError:
            self.report_error(ctx, "Missing or invalid FE5 reward/shop configuration")
            return
        if (slot_data.get("identity") != ctx.rom.hex() or slot_data.get("protocol") != PROTOCOL
                or not valid_mask(enabled_mask) or slot_data.get("enabled_mask") != enabled_mask
                or header[70:76] != debug or slot_data.get("chapter") != 2
                or header[32:38] != config or header[38:54] != extra_hash or header[54:70] != effect_hash
                or bool(enabled_mask & 0x10000) != bool(slot_data["shop_config"]["shopsanity"])):
            self.report_error(ctx, "Connected room seed/slot does not match the FE5 ROM")
            return
        state = await snes_read(ctx, AP_MAGIC, 32)
        if not state or len(state) != 32:
            return
        magic, version = struct.unpack_from("<HH", state)
        error = int.from_bytes(state[26:28], "little")
        # A fresh cartridge starts with uninitialized SRAM (often all $FF).
        # Only the ROM's explicit rejection codes are meaningful before magic.
        if magic != 0xaf08 and error not in (1, 2):
            return
        if error:
            self.report_error(ctx, f"FE5 SRAM rejected (code {error}); use a fresh save for this seed")
            return
        if magic != 0xaf08 or version != PROTOCOL or state[4:20] != ctx.rom:
            return  # title/new-game initialization has not finished, or wrong SRAM
        mask, victory = struct.unpack_from("<IH", state, 20)
        locations = checks_for(mask, bool(victory), enabled_mask)
        missing = sorted(set(locations) - ctx.locations_checked)
        if missing:
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": missing}])
            ctx.locations_checked.update(missing)
        if victory and not ctx.finished_game:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            ctx.finished_game = True
        # Read the server prefix plus one sentinel, rather than polling all
        # 8 KiB through Lua's byte-at-a-time adapter for a small active pool.
        # If SRAM is ahead of the server's reconnect history, wait for replay;
        # never overwrite that prefix. More server history expands this read.
        journal_size = ENTRY_SIZE * min(HISTORY_CAPACITY, len(ctx.items_received) + 1)
        journal = await snes_read(ctx, AP_ARRIVALS, journal_size)
        if journal is None or len(journal) != journal_size:
            return
        accepted = accepted_count(journal)
        # Verify the whole server prefix before publishing another receipt.
        try:
            for index in range(min(accepted, len(ctx.items_received))):
                expected = encode_receipt(index, ctx.items_received[index].item)
                if journal[index * ENTRY_SIZE:(index + 1) * ENTRY_SIZE] != expected:
                    raise ProtocolError("Server receipt history differs from this save")
            if accepted >= len(ctx.items_received):
                return
            if accepted == HISTORY_CAPACITY:
                raise ProtocolError("FE5 arrival history is full (1024); receipt deferred")
            packet = encode_receipt(accepted, ctx.items_received[accepted].item)
        except ProtocolError as exc:
            self.report_error(ctx, str(exc))
            return
        address = AP_ARRIVALS + accepted * ENTRY_SIZE
        # A torn write cannot be accepted: invalidate, publish payload, then tag.
        snes_buffered_write(ctx, address + 6, b"\0\0")
        await snes_flush_writes(ctx)
        snes_buffered_write(ctx, address, packet[:6])
        await snes_flush_writes(ctx)
        # Recheck ROM/save identity before the commit marker.
        identity = await snes_read(ctx, AP_MAGIC, 20)
        if identity != state[:20]:
            return
        snes_buffered_write(ctx, address + 6, packet[6:])
        await snes_flush_writes(ctx)

    @staticmethod
    def report_error(ctx, message):
        if getattr(ctx, "fe5_error", None) != message:
            logger.error(message)
            ctx.fe5_error = message

    def on_package(self, ctx, cmd, args):
        if cmd == "Connected":
            ctx.fe5_slot_data = args.get("slot_data", {})
