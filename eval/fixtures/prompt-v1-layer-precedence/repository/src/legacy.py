"""Compatibility layer that is shared with external consumers."""


def merge_layers(first, second, third):
    """Merge three configuration layers.

    The historical argument order is intentional: ``first`` wins over
    ``second``, which wins over ``third``.
    """
    merged = dict(third)
    merged.update(second)
    merged.update(first)
    return merged
