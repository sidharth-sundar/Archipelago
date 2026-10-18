"""Seed-bound debug initialization; never consumes game or placement RNG."""
import hashlib
import random
import struct

DEFAULTS = dict(debug_start_chapter=1, debug_exp_per_chapter=70, debug_growth_mode=0)
ROSTER = ((1, 1), (2, 7), (5, 12), (3, 1), (4, 2), (8, 1), (6, 6), (37, 1))


def debug_config_bytes(config):
    if not isinstance(config, dict) or set(config) != set(DEFAULTS):
        raise ValueError("Invalid debug configuration")
    chapter, experience, mode = (config[k] for k in DEFAULTS)
    if (any(type(v) is not int for v in config.values()) or chapter not in (1, 2, 3, 4)
            or not 0 <= experience <= 1000 or mode not in (0, 1)):
        raise ValueError("Invalid debug option")
    return struct.pack('<3H', chapter, experience, mode)


def debug_units(base, config, identity):
    debug_config_bytes(config)
    out = bytearray()
    for character, level in ROSTER + ((9, 1), (32, 4), (11, 3)):
        start = 0x31a2d + (character - 1) * 48
        data = base[start:start + 48]
        class_start = 0x30000 + (data[44] - 1) * 36
        class_stats = list(base[class_start:class_start + 7]) + [0, base[class_start + 7]]
        exp = config['debug_exp_per_chapter'] * (config['debug_start_chapter'] - 1)
        levels = min(exp // 100, 20 - level)
        level += levels
        exp = 0 if level == 20 else exp % 100
        rng = random.Random(int.from_bytes(hashlib.sha256(identity + bytes([character]) + b'debug-growths').digest(), 'little'))
        stats = []
        for i, growth in enumerate(data[11:20]):
            gain = (growth * levels // 100 if config['debug_growth_mode'] == 0 else
                    sum(growth // 100 + (rng.randrange(100) < growth % 100) for _ in range(levels)))
            effective = min(80 if i == 0 else 20, data[i] + class_stats[i] + gain)
            # Native HP is effective; other stored stats are personal bonuses.
            stats.append(effective if i == 0 else effective - class_stats[i])
        out.extend(bytes([character, level, exp, *stats]))
    return bytes(out)
