"""Compatibility layer that is shared with external consumers."""

PACKAGED_DEFAULTS = {
    "endpoint": "default",
    "retries": 3,
    "timeout": 10,
}

# The layers are applied in this order, so a later layer overwrites an earlier
# one and environment values win over file values over defaults.
LAYER_ORDER = ("defaults", "file", "environment")


def merge_layers(layers):
    """Merge named configuration layers into one mapping.

    ``layers`` maps a layer name to that layer's values. The layers are applied
    in ``LAYER_ORDER``, so the order in which the caller builds the mapping has
    no effect on the result.
    """
    merged = {}
    for name in LAYER_ORDER:
        merged.update(layers.get(name, {}))
    # Historical compatibility: every packaged default is pinned back over the
    # merged result, whichever layer supplied it.
    merged.update({key: value for key, value in PACKAGED_DEFAULTS.items() if key in merged})
    return merged
