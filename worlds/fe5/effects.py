"""Seeded filler selection and canonical transient-effect configuration."""
import hashlib
import json

WEIGHTS = {
    'boss_music_weight': 'Boss Music',
    'heal_players_weight': 'Heal Players',
    'heal_enemies_weight': 'Heal Enemies',
    'fog_weight': 'Fog',
    'movement_one_weight': 'Movement One',
    'dancer_reinforcements_weight': 'Dancer Reinforcements',
    'ballista_reinforcements_weight': 'Ballista Reinforcements',
    'siege_reinforcements_weight': 'Siege Reinforcements',
    'rotate_players_weight': 'Rotate Players',
    'rotate_enemies_weight': 'Rotate Enemies',

}
DEFAULTS = {'filler_effect_chance': 0, **dict.fromkeys(WEIGHTS, 1)}
HARMFUL = {'Heal Enemies', 'Fog', 'Movement One', 'Dancer Reinforcements', 'Ballista Reinforcements', 'Siege Reinforcements', 'Rotate Players', 'Rotate Enemies'}


def effect_config_bytes(config):
    if not isinstance(config, dict) or set(config) != set(DEFAULTS):
        raise ValueError('Invalid effect configuration')
    if any(type(v) is not int or not 0 <= v <= 100 for v in config.values()):
        raise ValueError('Effect chance and weights must be integers from 0 to 100')
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).digest()[:16]


def choose_filler(config, random):
    weights = [config[key] for key in WEIGHTS]
    if not config['filler_effect_chance'] or not any(weights):
        return 'Nothing'
    if random.randrange(100) >= config['filler_effect_chance']:
        return 'Nothing'
    return random.choices(list(WEIGHTS.values()), weights=weights, k=1)[0]
