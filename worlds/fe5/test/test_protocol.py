import unittest
from ..definitions import ITEMS, LOCATIONS, QUEUE_CAPACITY
from ..protocol import QueueModel, ProtocolError, accepted_count, encode_receipt, checks_for


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.q = QueueModel(b"0123456789abcdef")

    def receive_all(self):
        for n, item in enumerate(ITEMS):
            self.q.receive(self.q.identity, n, item["id"])

    def test_order_and_duplicates(self):
        self.receive_all()
        self.receive_all()
        self.q.player_phase()
        self.assertEqual(self.q.inventory, [i["native"] for i in ITEMS])
        self.q.player_phase()
        self.assertEqual(self.q.delivered, 5)

    def test_partial_writes(self):
        packet = encode_receipt(0, ITEMS[0]["id"])
        for length in range(8):
            self.q.journal[:] = bytes(len(self.q.journal))
            self.q.journal[:length] = packet[:length]
            self.assertEqual(accepted_count(self.q.journal), 0, length)
        self.q.journal[:8] = packet
        self.assertEqual(accepted_count(self.q.journal), 1)

    def test_bad_identity_unknown_item_and_gap(self):
        for identity, index, item in ((b"wrong", 0, ITEMS[0]["id"]),
                                      (self.q.identity, 0, -1), (self.q.identity, 1, ITEMS[0]["id"])):
            with self.assertRaises(ProtocolError):
                self.q.receive(identity, index, item)
        self.assertEqual(accepted_count(self.q.journal), 0)

    def test_full_inventory_defers_without_evicting(self):
        self.q.inventory = [99] * 7
        self.receive_all()
        self.q.player_phase()
        self.assertEqual(self.q.inventory, [99] * 7)
        self.assertEqual(len(self.q.pending), 5)
        self.q.inventory.pop()
        self.q.player_phase()
        self.assertEqual(self.q.inventory, [99] * 6 + [ITEMS[0]["native"]])
        self.assertEqual(self.q.delivered, 1)

    def test_unavailable_leif(self):
        self.receive_all()
        self.q.player_phase(leif_available=False)
        self.assertEqual(self.q.delivered, 0)

    def test_full_queues_no_overwrite(self):
        for n in range(QUEUE_CAPACITY):
            self.q.receive(self.q.identity, n, ITEMS[n % 5]["id"])
        self.q.player_phase(False)
        before = bytes(self.q.journal)
        self.assertEqual(len(self.q.pending), 16)
        with self.assertRaises(ProtocolError):
            self.q.receive(self.q.identity, 16, ITEMS[0]["id"])
        self.assertEqual(bytes(self.q.journal), before)

    def test_reconnect_replay_conflict(self):
        self.receive_all()
        before = bytes(self.q.journal)
        self.receive_all()
        self.assertEqual(bytes(self.q.journal), before)
        with self.assertRaises(ProtocolError):
            self.q.receive(self.q.identity, 0, ITEMS[1]["id"])

    def test_native_load_replays_only_unsaved_grants(self):
        self.q.save(0)
        self.receive_all()
        self.q.player_phase()
        self.q.load(0)
        self.assertEqual(self.q.inventory, [])
        self.q.player_phase()
        self.assertEqual(len(self.q.inventory), 5)
        self.q.save(3)
        self.q.load(3)
        self.q.player_phase()
        self.assertEqual(len(self.q.inventory), 5)

    def test_copy_delete_preserve_other_save(self):
        self.receive_all()
        self.q.player_phase()
        self.q.save(0)
        self.q.copy(0, 1)
        self.q.delete(0)
        self.q.load(1)
        self.q.player_phase()
        self.assertEqual(len(self.q.inventory), 5)

    def test_victory_reports_every_house_idempotently(self):
        for mask in (0, 3, 31):
            self.q.checks = mask
            self.q.seize()
            self.q.seize()
            self.assertEqual(checks_for(self.q.checks, self.q.victory), [l["id"] for l in LOCATIONS])
