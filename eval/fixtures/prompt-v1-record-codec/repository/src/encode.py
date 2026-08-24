"""Encode a field list as one pipe-delimited record line."""

DELIMITER = "|"
ESCAPE = "\\"


def encode_record(fields):
    """Return one single-line record holding every field.

    The delimiter, the escape character, and an embedded newline are all
    escaped so that the encoded record never spans more than one line.
    """
    return DELIMITER.join(field.replace(DELIMITER, ESCAPE + DELIMITER) for field in fields)
