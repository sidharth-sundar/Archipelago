from collections import Counter
from random import Random
import json
import unittest
from BaseClasses import ItemClassification
from ..effects import DEFAULTS, WEIGHTS, HARMFUL, choose_filler, effect_config_bytes
from ..definitions import ITEMS
from ..protocol import QueueModel, ProtocolError, encode_receipt, accepted_count
from .test_world import generate

BY_NAME = {i['name']: i for i in ITEMS}


class EffectTests(unittest.TestCase):
    def test_map_effects_are_ordered_once_and_never_inventory_items(self):
        names = ('Dancer Reinforcements', 'Ballista Reinforcements',
                 'Siege Reinforcements', 'Rotate Players', 'Rotate Enemies')
        q = QueueModel(b'0123456789abcdef')
        q.save(0)
        q.inventory = [99] * 7
        receipts = ['Vouge'] * 17 + list(names) * 2
        for index, name in enumerate(receipts):
            q.receive(q.identity, index, BY_NAME[name]['id'])
            q.receive(q.identity, index, BY_NAME[name]['id'])
        for index in range(10):
            q.player_phase(leif_available=False)
            self.assertEqual(q.effect_log, list(range(17, 18+index)))
            self.assertIsNone(q.active_effect)
            self.assertEqual(q.inventory, [99] * 7)
        q.load(0)
        for _ in range(12):
            q.player_phase(leif_available=False)
        self.assertEqual(q.effect_log, list(range(17, 27)))
        self.assertEqual(q.inventory, [])
        self.assertTrue(set(names) <= HARMFUL)

    def test_selection_and_validation(self):
        for key in DEFAULTS:
            for value in (-1, 101, True, 0.5):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    effect_config_bytes(DEFAULTS | {key: value})
        for key in WEIGHTS:
            config = dict.fromkeys(DEFAULTS, 0) | {'filler_effect_chance': 100, key: 1}
            self.assertEqual({choose_filler(config, Random(i)) for i in range(100)}, {WEIGHTS[key]})
        self.assertEqual(choose_filler(dict.fromkeys(DEFAULTS, 0) | {'filler_effect_chance': 100}, Random(1)), 'Nothing')
        a, b = Random(42), Random(42)
        config = DEFAULTS | {'filler_effect_chance': 50}
        first = [choose_filler(config, a) for _ in range(100)]
        self.assertEqual(first, [choose_filler(config, b) for _ in range(100)])
        self.assertEqual(set(first), {'Nothing', *WEIGHTS.values()})

    def test_pool_classification_defaults_and_multiplayer(self):
        for chance in (0, 100):
            world = generate(2, options={1: {'filler_effect_chance': chance, 'shopsanity': 1}})
            items = [l.item for l in world.get_locations() if l.address is not None]
            for player in (1, 2):
                pool = [i for i in items if i.player == player]
                effects = [i for i in pool if i.name in WEIGHTS.values()]
                self.assertEqual(len(effects), 18 if player == 1 and chance == 100 else 0)
                for item in effects:
                    self.assertEqual(item.classification, ItemClassification.trap if item.name in HARMFUL else ItemClassification.filler)
        cfg = {'filler_effect_chance': 100, 'shopsanity': 1, 'enable_extra_valuable_items': 1,
               'extra_arms_scrolls': 9, 'extra_critical_manuals': 9}
        exact = generate(options={1: cfg})
        self.assertFalse(any(l.item.name in WEIGHTS.values() for l in exact.get_locations()))
        with self.assertRaisesRegex(ValueError, 'exceeds capacity by 1'):
            generate(options={1: cfg | {'extra_boots': 1}})
        off = dict.fromkeys(('recruitment_checks','village_checks','conversation_checks','chapter_completion_checks','ground_pickup'), 0)
        self.assertEqual(sum(l.address is not None for l in generate(options={1:off | {'filler_effect_chance':100}}).get_locations()), 0)

    def test_seeded_placements_and_relative_weights(self):
        options = {1: {'shopsanity': 1, 'filler_effect_chance': 100}}
        a, b = generate(seed=2026101800, options=options), generate(seed=2026101800, options=options)
        def placements(world):
            return [(l.name, l.item.name, l.item.player) for l in world.get_locations()]
        self.assertEqual(placements(a), placements(b))
        config = dict.fromkeys(DEFAULTS, 0) | {'filler_effect_chance': 100,
                                             'boss_music_weight': 100, 'fog_weight': 1}
        rng = Random(42)
        counts = Counter(choose_filler(config, rng) for _ in range(1000))
        self.assertGreater(counts['Boss Music'], 950)
        self.assertGreater(counts['Fog'], 0)
        self.assertEqual(set(counts), {'Boss Music', 'Fog'})

    def test_stable_effect_ids_and_identity(self):
        self.assertEqual([BY_NAME[n]['id'] for n in WEIGHTS.values()], list(range(16666642, 16666652)))
        a, b = generate(seed=2), generate(seed=2, options={1: {'fog_weight': 0}})
        self.assertNotEqual(a.worlds[1].identity, b.worlds[1].identity)
        self.assertEqual(b.worlds[1].fill_slot_data()['effects']['fog_weight'], 0)
        for name in WEIGHTS.values():
            packet = encode_receipt(0, BY_NAME[name]['id'])
            for cut in range(8):
                self.assertEqual(accepted_count(packet[:cut] + bytes(8-cut)), 0)
            self.assertEqual(accepted_count(packet), 1)

    def test_independent_queues_wrap_and_final_receipt(self):
        q = QueueModel(b'0123456789abcdef')
        q.inventory = [99]*7
        # More than a full physical ring before the first effect.
        names = ['Vouge']*17 + ['Fog']*1007
        for i,name in enumerate(names):
            q.receive(q.identity, i, BY_NAME[name]['id'])
            q.receive(q.identity, i, BY_NAME[name]['id'])
        q.player_phase(False)
        self.assertEqual(q.effect_log, [17])
        self.assertEqual(len(q.pending), 16)
        self.assertEqual(len(q.effect_pending), 15)
        for _ in range(1006): q.player_phase(False)
        self.assertEqual(q.effect_log, list(range(17, 1024)))
        self.assertEqual(q.delivered, 0)
        self.assertEqual(q.consumed_effects[-1], 255)
        with self.assertRaises(ProtocolError): q.receive(q.identity, 1024, BY_NAME['Fog']['id'])
        for _ in range(3):
            q.inventory.clear(); q.player_phase()
        self.assertEqual(q.delivered, 1024)

    def test_native_replay_suspend_copy_delete_and_interrupt(self):
        q = QueueModel(b'0123456789abcdef')
        q.save(0)
        for i,name in enumerate(('Vouge','Fog','Heal Players','Movement One')):
            q.receive(q.identity,i,BY_NAME[name]['id'])
        q.player_phase()
        self.assertEqual(q.effect_log,[1])
        self.assertEqual(q.inventory,[BY_NAME['Vouge']['native']])
        q.save(3);q.copy(3,1);q.delete(3);q.load(1)
        self.assertEqual(q.active_effect, BY_NAME['Fog']['native'])
        self.assertEqual(q.effect_log,[1])  # load is not a new phase
        q.load(0);self.assertIsNone(q.active_effect)
        q.player_phase(interrupt_after_consumption=True)
        q.load(0);q.player_phase()
        self.assertEqual(q.effect_log,[1,3])  # interrupted heal is consumed, not replayed
        self.assertEqual(q.inventory,[BY_NAME['Vouge']['native']])
        q.player_phase();self.assertIsNone(q.active_effect)
        q.seize();q.receive(q.identity,4,BY_NAME['Fog']['id']);q.player_phase()
        self.assertEqual(q.effect_log,[1,3])

    def test_phase_boundary_defers_late_receipts(self):
        q=QueueModel(b'0123456789abcdef')
        q.receive(q.identity,0,BY_NAME['Boss Music']['id'])
        q.player_phase(after_boundary=lambda:q.receive(q.identity,1,BY_NAME['Vouge']['id']))
        self.assertEqual(q.effect_log,[0]);self.assertEqual(q.inventory,[])
        q.player_phase();self.assertEqual(q.inventory,[BY_NAME['Vouge']['native']])

