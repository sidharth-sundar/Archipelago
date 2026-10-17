import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from ..client import FE5SNIClient
from ..connector_config import ROM_HEADER, AP_MAGIC, AP_ARRIVALS
from ..definitions import ITEMS, LOCATIONS, PROTOCOL
from ..protocol import encode_receipt


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.identity = bytes.fromhex("00112233445566778899aabbccddeeff")
        self.header = b"FE5AP002" + self.identity + struct.pack("<HHH", PROTOCOL, 1, 0xffff)
        self.state = bytearray(struct.pack("<HH", 0xaf05, PROTOCOL) + self.identity + bytes(12))
        self.journal = bytearray(128)
        self.sent = []
        self.writes = []
        self.flushes = 0
        async def send(messages):
            self.sent.extend(messages)
        self.ctx = SimpleNamespace(server=object(), slot=1, rom=self.identity, locations_checked=set(),
                                   finished_game=False, fe5_slot_data={"identity": self.identity.hex(), "protocol": PROTOCOL, "enabled_mask": 0xffff},
                                   items_received=[], send_msgs=send)
        async def read(ctx, address, size):
            if address == ROM_HEADER:
                return self.header[:size]
            if address == AP_MAGIC:
                return bytes(self.state[:size])
            if address == AP_ARRIVALS:
                return bytes(self.journal[:size])
            raise AssertionError(f"Unexpected read {address:x}")
        def write(ctx, address, data):
            self.writes.append((address, data))
            offset = address - AP_ARRIVALS
            self.journal[offset:offset + len(data)] = data
        async def flush(ctx):
            self.flushes += 1
        self.transport = SimpleNamespace(snes_read=read, snes_buffered_write=write, snes_flush_writes=flush)
        self.patcher = patch.dict(sys.modules, {"SNIClient": self.transport})
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.client = FE5SNIClient()

    async def test_receipt_commit_last_and_duplicate(self):
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[0]["id"])]
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.journal[:8], encode_receipt(0, ITEMS[0]["id"]))
        self.assertEqual(self.writes[0], (AP_ARRIVALS + 6, b"\0\0"))
        self.assertEqual(self.writes[-1][0], AP_ARRIVALS + 6)
        self.assertEqual(self.flushes, 3)
        self.writes.clear()
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.writes, [])

    async def test_wrong_seed_and_slot_write_nothing(self):
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[0]["id"])]
        self.ctx.fe5_slot_data["identity"] = "wrong"
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.writes, [])
        self.assertEqual(self.sent, [])
        self.ctx.fe5_slot_data["identity"] = self.identity.hex()
        self.ctx.slot = 2
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.writes, [])

    async def test_victory_reports_checks_before_goal(self):
        self.state[22:24] = b"\x01\0"
        await self.client.game_watcher(self.ctx)
        self.assertEqual(len(self.sent[0]["locations"]), 16)
        self.assertEqual(self.sent[1]["cmd"], "StatusUpdate")
        self.sent.clear()
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.sent, [])

    async def test_unknown_item_never_written(self):
        self.ctx.items_received = [SimpleNamespace(item=-99)]
        with patch("worlds.fe5.client.logger.error") as error:
            for _ in range(2):
                self.assertTrue(await self.client.validate_rom(self.ctx))
                await self.client.game_watcher(self.ctx)
            self.assertEqual(error.call_count, 1)
        self.assertEqual(self.writes, [])

    async def test_connected_package_retains_slot_data(self):
        self.ctx.fe5_slot_data = {}
        self.client.on_package(self.ctx, "Connected", {"slot_data": {"identity": self.identity.hex(), "protocol": PROTOCOL, "enabled_mask": 0xffff}})
        self.assertEqual(self.ctx.fe5_slot_data["identity"], self.identity.hex())

    async def test_fresh_sram_waits_but_explicit_rejection_is_reported(self):
        initialized = self.state[:]
        with patch("worlds.fe5.client.logger.error") as error:
            for value in (0, 255):
                self.state[:] = bytes([value]) * 32
                await self.client.game_watcher(self.ctx)
            error.assert_not_called()
            self.assertEqual(self.writes, [])
            self.state[24:26] = b"\x01\0"
            await self.client.game_watcher(self.ctx)
            error.assert_called_once()
        self.state[:] = initialized
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[0]["id"])]
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.journal[:8], encode_receipt(0, ITEMS[0]["id"]))

    async def test_mask_mismatch_and_disabled_checks(self):
        self.state[20:24] = b"\xff\xff\x01\0"
        self.header = self.header[:28] + b"\0\xe0"
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.writes, [])
        self.ctx.fe5_slot_data["enabled_mask"] = 0xe000
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.sent[0]["locations"], [l["id"] for l in LOCATIONS[13:]])

    async def test_full_journal_with_nothing_and_reconnect(self):
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[-1]["id"]) for _ in range(16)]
        for _ in range(16):
            await self.client.game_watcher(self.ctx)
        expected = bytes(self.journal)
        self.writes.clear()
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.writes, [])
        self.journal[80:] = bytes(48)  # older complete SRAM snapshot: refill its missing suffix
        for _ in range(6):
            await self.client.game_watcher(self.ctx)
        self.assertEqual(bytes(self.journal), expected)

    async def test_interrupted_payload_retried(self):
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[-1]["id"])]
        packet = encode_receipt(0, ITEMS[-1]["id"])
        for size in range(8):
            self.journal[:] = bytes(128)
            self.journal[:size] = packet[:size]
            await self.client.game_watcher(self.ctx)
            self.assertEqual(self.journal[:8], packet)
