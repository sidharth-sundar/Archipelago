"""Canonical extra reward configuration, also usable by the standalone patcher."""
import hashlib
import json

BOOSTERS = {
    "extra_life_rings": "Life Ring", "extra_speed_rings": "Speed Ring",
    "extra_magic_rings": "Magic Ring", "extra_strength_rings": "Strength Ring",
    "extra_luck_rings": "Luck Ring", "extra_skill_rings": "Skill Ring",
    "extra_shield_rings": "Shield Ring", "extra_body_rings": "Body Ring", "extra_boots": "Boots",
}
STAVES = {"extra_warp_staves": "Warp", "extra_rescue_staves": "Rescue"}
COUNTS = BOOSTERS | STAVES
FLAGS = ("enable_extra_valuable_items", "random_stat_boosters", "exclude_boots_from_random_stat_boosters")
DEFAULTS = dict.fromkeys((*FLAGS, *COUNTS, "random_stat_booster_count"), 0)


def resolve_extra_items(values, random):
    """Ignore disabled controls before drawing; return only effective settings."""
    config = dict(DEFAULTS)
    if values["enable_extra_valuable_items"]:
        config.update(values)
        if config["random_stat_boosters"]:
            for key in BOOSTERS:
                config[key] = 0
        else:
            config["random_stat_booster_count"] = 0
            config["exclude_boots_from_random_stat_boosters"] = 0
    counts = {name: config[key] for key, name in COUNTS.items()}
    if config["random_stat_boosters"]:
        choices = [name for name in BOOSTERS.values()
                   if name != "Boots" or not config["exclude_boots_from_random_stat_boosters"]]
        for _ in range(config["random_stat_booster_count"]):
            counts[random.choice(choices)] += 1
    config["resolved_counts"] = counts
    extra_config_bytes(config)  # validate even when called outside option parsing
    return config


def extra_config_bytes(config):
    if not isinstance(config, dict) or set(config) != set(DEFAULTS) | {"resolved_counts"}:
        raise ValueError("Invalid extra-item configuration")
    for key in DEFAULTS:
        limit = 1 if key in FLAGS else 3 if key in STAVES else 9
        if type(config[key]) is not int or not 0 <= config[key] <= limit:
            raise ValueError(f"Invalid extra-item option: {key}")
    counts = config["resolved_counts"]
    if not isinstance(counts, dict) or set(counts) != set(COUNTS.values()):
        raise ValueError("Invalid resolved extra-item counts")
    for key, name in COUNTS.items():
        if type(counts[name]) is not int or not 0 <= counts[name] <= (3 if key in STAVES else 9):
            raise ValueError("Invalid resolved extra-item count")
    if not config["enable_extra_valuable_items"] and (any(config[k] for k in DEFAULTS) or any(counts.values())):
        raise ValueError("Disabled extras must have zero effective counts")
    if config["random_stat_boosters"]:
        if any(config[k] for k in BOOSTERS) or sum(counts[n] for n in BOOSTERS.values()) != config["random_stat_booster_count"]:
            raise ValueError("Random booster configuration disagrees with resolved counts")
        if config["exclude_boots_from_random_stat_boosters"] and counts["Boots"]:
            raise ValueError("Excluded Boots present in random results")
    elif config["random_stat_booster_count"] or config["exclude_boots_from_random_stat_boosters"] or any(
            config[k] != counts[n] for k, n in BOOSTERS.items()):
        raise ValueError("Manual booster configuration disagrees with resolved counts")
    if any(config[k] != counts[n] for k, n in STAVES.items()):
        raise ValueError("Staff configuration disagrees with resolved counts")
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).digest()[:16]
