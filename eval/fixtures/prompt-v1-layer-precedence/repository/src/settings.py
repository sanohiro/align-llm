"""Effective settings for one run."""

from legacy import merge_layers


def resolve_settings(defaults, file_values, env_values):
    """Return the effective settings for one run.

    Precedence is environment values over file values over defaults.
    """
    return merge_layers({
        "defaults": defaults,
        "file": file_values,
        "environment": env_values,
    })
