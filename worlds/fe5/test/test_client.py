import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from ..client import FE5SNIClient
from ..connector_config import ROM_HEADER, AP_MAGIC, AP_ARRIVALS
from ..definitions import ITEMS, LOCATIONS, PROTOCOL
from ..protocol import encode_receipt
from ..patchcore import shop_config_bytes
from ..definitions import HISTORY_CAPACITY


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.identity = bytes.fromhex("00112233445566778899aabbccddeeff")
        self.config = dict(armorysanity=0, shopsanity=0, armory_items_in_pool=1, shop_items_in_pool=1, armory_price_multiplier=10, shop_price_multiplier=10)
        self.header = b"FE5AP003" + self.identity + struct.pack("<HHI", PROTOCOL, 1, 0xffff) + shop_config_bytes(self.config)
        self.state = bytearray(struct.pack("<HH", 0xaf05, PROTOCOL) + self.identity + bytes(12))
        self.journal = bytearray(HISTORY_CAPACITY * 8)
        self.sent = []
        self.writes = []
        self.flushes = 0
        async def send(messages):
            self.sent.extend(messages)
        self.ctx = SimpleNamespace(server=object(), slot=1, rom=self.identity, locations_checked=set(),
                                   finished_game=False, fe5_slot_data={"identity": self.identity.hex(), "protocol": PROTOCOL, "enabled_mask": 0xffff, "shop_config": self.config},
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
        self.state[24:26] = b"\x01\0"
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
        self.client.on_package(self.ctx, "Connected", {"slot_data": {"identity": self.identity.hex(), "protocol": PROTOCOL, "enabled_mask": 0xffff, "shop_config": self.config}})
        self.assertEqual(self.ctx.fe5_slot_data["identity"], self.identity.hex())

    async def test_fresh_sram_waits_but_explicit_rejection_is_reported(self):
        initialized = self.state[:]
        with patch("worlds.fe5.client.logger.error") as error:
            for value in (0, 255):
                self.state[:] = bytes([value]) * 32
                await self.client.game_watcher(self.ctx)
            error.assert_not_called()
            self.assertEqual(self.writes, [])
            self.state[26:28] = b"\x01\0"
            await self.client.game_watcher(self.ctx)
            error.assert_called_once()
        self.state[:] = initialized
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[0]["id"])]
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.journal[:8], encode_receipt(0, ITEMS[0]["id"]))

    async def test_mask_mismatch_and_disabled_checks(self):
        self.state[20:26] = struct.pack("<IH", 0xffff, 1)
        self.config = dict(armorysanity=0, shopsanity=0, armory_items_in_pool=1, shop_items_in_pool=1, armory_price_multiplier=10, shop_price_multiplier=10)
        self.header = self.header[:28] + struct.pack("<I", 0xe000) + shop_config_bytes(self.config)
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.writes, [])
        self.ctx.fe5_slot_data["enabled_mask"] = 0xe000
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.sent[0]["locations"], [l["id"] for l in LOCATIONS[13:16]])

    async def test_full_journal_with_nothing_and_reconnect(self):
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[-1]["id"]) for _ in range(16)]
        for _ in range(16):
            await self.client.game_watcher(self.ctx)
        expected = bytes(self.journal)
        self.writes.clear()
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.writes, [])
        self.journal[80:] = bytes(len(self.journal) - 80)  # older complete SRAM snapshot: refill its missing suffix
        for _ in range(6):
            await self.client.game_watcher(self.ctx)
        self.assertEqual(bytes(self.journal), expected)

    async def test_interrupted_payload_retried(self):
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[-1]["id"])]
        packet = encode_receipt(0, ITEMS[-1]["id"])
        for size in range(8):
            self.journal[:] = bytes(HISTORY_CAPACITY * 8)
            self.journal[:size] = packet[:size]
            await self.client.game_watcher(self.ctx)
            self.assertEqual(self.journal[:8], packet)

    async def test_price_configuration_mismatch_never_sends_or_receives(self):
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[0]["id"])]
        self.state[24:26] = b"\x01\0"
        self.ctx.fe5_slot_data["shop_config"] = dict(self.config, shop_price_multiplier=4)
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.writes, [])
        self.assertEqual(self.sent, [])

    async def test_seventeenth_check_and_final_receipt(self):
        config = dict(self.config, shopsanity=1)
        self.header = self.header[:28] + struct.pack("<I", 0x1ffff) + shop_config_bytes(config)
        self.ctx.fe5_slot_data.update(enabled_mask=0x1ffff, shop_config=config)
        self.state[20:26] = struct.pack("<IH", 0x10000, 0)
        self.ctx.items_received = [SimpleNamespace(item=ITEMS[-1]['id']) for _ in range(HISTORY_CAPACITY)]
        for index in range(HISTORY_CAPACITY - 1):
            self.journal[index * 8:index * 8 + 8] = encode_receipt(index, ITEMS[-1]['id'])
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.sent[0]['locations'], [LOCATIONS[-1]['id']])
        self.assertEqual(self.journal[-8:], encode_receipt(1023, ITEMS[-1]['id']))
        self.writes.clear()
        await self.client.game_watcher(self.ctx)
        self.assertEqual(self.writes, [])
