"""Audit information only; inventory capacity does not constrain generation."""
CONVOY_CAPACITY = 512
AUDIT_THRESHOLD = 154


def capacity_report(guaranteed, extras, physical_filler):
    counts = (guaranteed, extras, physical_filler)
    if any(type(n) is not int or n < 0 for n in counts):
        raise ValueError("Physical contribution counts must be nonnegative integers")
    total = sum(counts)
    return dict(guaranteed_physical=guaranteed, configured_extras=extras,
                physical_filler=physical_filler, total=total,
                convoy_capacity=CONVOY_CAPACITY, audit_threshold=AUDIT_THRESHOLD,
                audit_recommended=total >= AUDIT_THRESHOLD)
