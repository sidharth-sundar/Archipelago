"""Wire format shared by SNI and protocol tests; no emulator or AP imports.

An immutable 1,024-entry journal supports replay after native save loads.
The separate 16-entry pending ring may wrap; history must never be overwritten.
"""
from dataclasses import dataclass, field
import struct
from .definitions import ITEMS, LOCATIONS, HISTORY_CAPACITY, PENDING_CAPACITY

NATIVE_ITEMS = {item["id"]: item["native"] for item in ITEMS}
EFFECT_CODES = {i["native"] for i in ITEMS if 0xff00 <= i["native"] < 0xffff}
ALL_CHECKS = (1 << len(LOCATIONS)) - 1
ENTRY_SIZE = 8


class ProtocolError(ValueError):
    pass


def encode_receipt(index: int, item_id: int) -> bytes:
    if not 0 <= index < HISTORY_CAPACITY:
        raise ProtocolError("Arrival journal full; unread receipts must not be overwritten")
    try:
        native = NATIVE_ITEMS[item_id]
    except KeyError as exc:
        raise ProtocolError(f"Unknown FE5 item ID: {item_id}") from exc
    return struct.pack("<4H", index, native, index ^ native ^ 0x5AA5, 0xA500 ^ index)


def decode_receipt(data: bytes, index: int) -> int | None:
    if len(data) != ENTRY_SIZE or not 0 <= index < HISTORY_CAPACITY:
        return None
    seq, native, check, commit = struct.unpack("<4H", data)
    if (seq != index or native not in NATIVE_ITEMS.values()
            or check != seq ^ native ^ 0x5AA5 or commit != 0xA500 ^ index):
        return None
    return native


def accepted_count(journal: bytes) -> int:
    for index in range(HISTORY_CAPACITY):
        if decode_receipt(journal[index * ENTRY_SIZE:(index + 1) * ENTRY_SIZE], index) is None:
            return index
    return HISTORY_CAPACITY


def checks_for(mask: int, victory: bool, enabled_mask: int = ALL_CHECKS) -> list[int]:
    return [l["id"] for l in LOCATIONS
            if enabled_mask & (1 << l["bit"]) and (victory or mask & (1 << l["bit"]))]


@dataclass
class QueueModel:
    """Executable reference model for ROM/client invariants, not an emulator.

    Save snapshots pair inventory and cursor atomically; arrival history and
    offline checks are seed-global and deliberately do not rewind on load.
    """
    identity: bytes
    enabled_mask: int = ALL_CHECKS
    journal: bytearray = field(default_factory=lambda: bytearray(ENTRY_SIZE * HISTORY_CAPACITY))
    applied: bytearray = field(default_factory=lambda: bytearray(HISTORY_CAPACITY // 8))
    pending: list[int] = field(default_factory=list)
    processed: int = 0
    delivered: int = 0
    inventory: list[int] = field(default_factory=list)
    checks: int = 0
    victory: bool = False
    saves: dict = field(default_factory=dict)
    consumed_effects: bytearray = field(default_factory=lambda: bytearray(HISTORY_CAPACITY // 8))
    effect_scan: int = 0
    effect_pending: list[int] = field(default_factory=list)
    effect_log: list[int] = field(default_factory=list)
    active_effect: int | None = None
    phase_limit: int = 0
    turn: int = 0
    expiry: int = 0

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
        accepted = self.phase_limit
        while self.processed < accepted and len(self.pending) < PENDING_CAPACITY:
            i = self.processed
            self.pending.append(i)
            self.processed += 1

    def stage_effects(self):
        while self.effect_scan < self.phase_limit and len(self.effect_pending) < PENDING_CAPACITY:
            i = self.effect_scan
            if self.receipt(i) in EFFECT_CODES and not self.consumed_effects[i // 8] & (1 << (i % 8)):
                self.effect_pending.append(i)
            self.effect_scan += 1

    def receipt(self, index):
        return decode_receipt(self.journal[index * ENTRY_SIZE:(index + 1) * ENTRY_SIZE], index)

    def player_phase(self, leif_available=True, interrupt_after_consumption=False, after_boundary=None):
        if self.victory:
            return
        self.turn += 1
        if self.turn >= self.expiry:
            self.active_effect = None
        self.phase_limit = accepted_count(self.journal)
        if after_boundary:
            after_boundary()
        self.stage_effects()
        while self.effect_pending:
            i = self.effect_pending[0]
            mask = 1 << (i % 8)
            if self.consumed_effects[i // 8] & mask:
                self.effect_pending.pop(0)
                continue
            self.consumed_effects[i // 8] |= mask
            if interrupt_after_consumption:
                return
            self.effect_pending.pop(0)
            self.effect_log.append(i)
            code = self.receipt(i)
            if code in (0xff00, 0xff03, 0xff04):
                self.active_effect, self.expiry = code, self.turn + 1
            break
        while True:
            self.stage()
            if not self.pending:
                return
            byte, bit = divmod(self.delivered, 8)
            if self.applied[byte] & (1 << bit) or self.receipt(self.pending[0]) == 0xffff or self.receipt(self.pending[0]) in EFFECT_CODES:
                self.pending.pop(0)
            elif leif_available and len(self.inventory) < 7:
                self.inventory.append(self.receipt(self.pending.pop(0)))
            else:
                break
            self.applied[byte] |= 1 << bit
            self.delivered += 1

    def seize(self):
        self.checks = self.enabled_mask
        self.victory = True
        self.active_effect = None

    def save(self, slot):
        self.saves[slot] = (self.processed, self.delivered, list(self.pending), list(self.inventory), bytes(self.applied), self.active_effect, self.turn, self.expiry)

    def load(self, slot):
        p, d, pending, inventory, applied, self.active_effect, self.turn, self.expiry = self.saves[slot]
        self.processed, self.delivered = p, d
        self.pending, self.inventory = list(pending), list(inventory)
        self.applied[:] = applied
        self.phase_limit = 0

    def copy(self, source, destination):
        self.saves[destination] = self.saves[source]

    def delete(self, slot):
        self.saves.pop(slot, None)
