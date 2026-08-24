"""Decode one pipe-delimited record line back into its fields."""

DELIMITER = "|"
ESCAPE = "\\"


def decode_record(line):
    """Return the fields encoded in one record line."""
    fields = []
    current = []
    escaped = False
    for character in line:
        if escaped:
            current.append(character)
            escaped = False
        elif character == ESCAPE:
            escaped = True
        elif character == DELIMITER:
            fields.append("".join(current))
            current = []
        else:
            current.append(character)
    if escaped:
        raise ValueError("record line ends with a dangling escape")
    fields.append("".join(current))
    return fields
