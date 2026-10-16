"""Wire format shared by SNI and protocol tests; no emulator or AP imports.

v0 has only five receipts. The 16-entry arrival journal is append-only for the
entire seed: retaining entries allows a native save load to replay exactly the
receipts that are absent from that save. It must never wrap or overwrite.
"""
from dataclasses import dataclass, field
import struct
from .definitions import ITEMS, LOCATIONS, QUEUE_CAPACITY

NATIVE_ITEMS = {item["id"]: item["native"] for item in ITEMS}
ALL_CHECKS = (1 << len(LOCATIONS)) - 1
ENTRY_SIZE = 8


class ProtocolError(ValueError):
    pass


def encode_receipt(index: int, item_id: int) -> bytes:
    if not 0 <= index < QUEUE_CAPACITY:
        raise ProtocolError("Arrival journal full; unread receipts must not be overwritten")
    try:
        native = NATIVE_ITEMS[item_id]
    except KeyError as exc:
        raise ProtocolError(f"Unknown FE5 item ID: {item_id}") from exc
    return struct.pack("<4H", index, native, index ^ native ^ 0x5AA5, 0xA500 | (index + 1))


def decode_receipt(data: bytes, index: int) -> int | None:
    if len(data) != ENTRY_SIZE or not 0 <= index < QUEUE_CAPACITY:
        return None
    seq, native, check, commit = struct.unpack("<4H", data)
    if (seq != index or native not in NATIVE_ITEMS.values()
            or check != seq ^ native ^ 0x5AA5 or commit != 0xA500 | (index + 1)):
        return None
    return native


def accepted_count(journal: bytes) -> int:
    for index in range(QUEUE_CAPACITY):
        if decode_receipt(journal[index * ENTRY_SIZE:(index + 1) * ENTRY_SIZE], index) is None:
            return index
    return QUEUE_CAPACITY


def checks_for(mask: int, victory: bool) -> list[int]:
    return [l["id"] for l in LOCATIONS if victory or mask & (1 << l["bit"])]


@dataclass
class QueueModel:
    """Executable reference model for ROM/client invariants, not an emulator.

    Save snapshots pair inventory and cursor atomically; arrival history and
    offline checks are seed-global and deliberately do not rewind on load.
    """
    identity: bytes
    journal: bytearray = field(default_factory=lambda: bytearray(ENTRY_SIZE * QUEUE_CAPACITY))
    pending: list[int] = field(default_factory=list)
    processed: int = 0
    delivered: int = 0
    inventory: list[int] = field(default_factory=list)
    checks: int = 0
    victory: bool = False
    saves: dict = field(default_factory=dict)

    def receive(self, identity: bytes, index: int, item_id: int):
        if identity != self.identity:
            raise ProtocolError("Seed/slot identity mismatch")
        packet = encode_receipt(index, item_id)
        accepted = accepted_count(self.journal)
        start = index * ENTRY_SIZE
        if index < accepted:
            if self.journal[start:start + ENTRY_SIZE] != packet:
                raise ProtocolError("Conflicting replay of accepted receipt")
            return
        if index != accepted:
            raise ProtocolError("Receipt order gap")
        self.journal[start:start + ENTRY_SIZE] = packet

    def stage(self):
        accepted = accepted_count(self.journal)
        while self.processed < accepted and len(self.pending) < QUEUE_CAPACITY:
            i = self.processed
            self.pending.append(decode_receipt(self.journal[i * ENTRY_SIZE:(i + 1) * ENTRY_SIZE], i))
            self.processed += 1

    def player_phase(self, leif_available=True):
        self.stage()
        while leif_available and self.pending and len(self.inventory) < 7:
            self.inventory.append(self.pending.pop(0))
            self.delivered += 1

    def seize(self):
        self.checks = ALL_CHECKS
        self.victory = True

    def save(self, slot):
        self.saves[slot] = (self.processed, self.delivered, list(self.pending), list(self.inventory))

    def load(self, slot):
        p, d, pending, inventory = self.saves[slot]
        self.processed, self.delivered = p, d
        self.pending, self.inventory = list(pending), list(inventory)

    def copy(self, source, destination):
        self.saves[destination] = self.saves[source]

    def delete(self, slot):
        self.saves.pop(slot, None)
