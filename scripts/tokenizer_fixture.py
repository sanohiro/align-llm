#!/usr/bin/env python3
"""Build the bounded synthetic GGUF vocabulary owned by R7-TOKENIZER.

The fixture is generated at test time and uses the independent GGUF writer from
``scripts/gguf_fixture.py``.  Its byte alphabet and expected ids are computed here rather than
from the Align implementation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import unicodedata

from gguf_fixture import Array, Container, INT32, Kv, STRING, i32v, strv


def byte_scalar(value: int) -> int:
    direct = 33 <= value <= 126 or 161 <= value <= 172 or 174 <= value <= 255
    if direct:
        return value
    rank = sum(
        1
        for candidate in range(value)
        if not (33 <= candidate <= 126 or 161 <= candidate <= 172 or 174 <= candidate <= 255)
    )
    return 256 + rank


def byte_spelling(value: int) -> str:
    return chr(byte_scalar(value))


def fixture_data() -> tuple[list[str], list[int], list[str]]:
    tokens = [byte_spelling(value) for value in range(256)]
    types = [1] * len(tokens)

    additions = [
        ("he", 1),
        ("hel", 1),
        ("hell", 1),
        ("hello", 1),
        ("<UNK>", 2),
        ("<CTRL>", 3),
        ("<USER>", 4),
        ("xy", 5),
        ("<0xFF>", 6),
        ("<0x41>", 6),
        ("</s>", 1),
    ]
    for spelling, token_type in additions:
        tokens.append(spelling)
        types.append(token_type)

    merges = ["h e", "he l", "hel l", "hell o", "x y"]
    return tokens, types, merges


def write_model(
    destination: Path,
    tokens: list[str],
    types: list[int],
    merges: list[str],
    *,
    model: str = "gpt2",
    pre: str = "qwen2",
    chat_template: str | None = None,
) -> None:
    kvs = [
        Kv("tokenizer.ggml.model", strv(model)),
        Kv("tokenizer.ggml.pre", strv(pre)),
        Kv("tokenizer.ggml.tokens", Array(STRING, [strv(value) for value in tokens])),
        Kv("tokenizer.ggml.token_type", Array(INT32, [i32v(value) for value in types])),
        Kv("tokenizer.ggml.merges", Array(STRING, [strv(value) for value in merges])),
    ]
    if chat_template is not None:
        kvs.append(Kv("tokenizer.chat_template", strv(chat_template)))
    write_kvs(destination, kvs)


def write_kvs(destination: Path, kvs: list[Kv]) -> None:
    container = Container(kvs, [], data_len=0)
    destination.write_bytes(container.bytes)


def build(output: Path) -> dict[str, object]:
    tokens, types, merges = fixture_data()
    model_path = output / "qwen2-tokenizer.gguf"
    write_model(model_path, tokens, types, merges)

    ids = {spelling: tokens.index(spelling) for spelling in tokens[256:]}
    return {
        "model": model_path.name,
        "vocab_size": len(tokens),
        "merge_count": len(merges),
        "ids": ids,
        "byte_ids": {"space": 32, "h": 104, "e": 101, "x": 120, "y": 121},
    }


def qwen_pieces(text: str) -> list[str]:
    classes = []
    for scalar in text:
        category = unicodedata.category(scalar)
        if category.startswith("L"):
            classes.append(1)
        elif category.startswith("N"):
            classes.append(2)
        elif scalar.isspace():
            classes.append(3)
        else:
            classes.append(0)
    pieces: list[str] = []
    at = 0
    while at < len(text):
        start = at
        contraction = -1
        if text[at] == "'" and at + 1 < len(text):
            one = text[at + 1].lower() if text[at + 1] in "STR EVMLD".replace(" ", "") else text[at + 1]
            if one in ("s", "t", "m", "d"):
                contraction = at + 2
            elif at + 2 < len(text):
                two = text[at + 2].lower() if text[at + 2] in "STREVMLD" else text[at + 2]
                if one + two in ("re", "ve", "ll"):
                    contraction = at + 3
        if contraction > at:
            pieces.append(text[start:contraction])
            at = contraction
            continue
        letter_at = at
        if classes[at] not in (1, 2) and text[at] not in "\r\n" and at + 1 < len(text) and classes[at + 1] == 1:
            letter_at = at + 1
        if classes[letter_at] == 1:
            end = letter_at + 1
            while end < len(text) and classes[end] == 1:
                end += 1
            pieces.append(text[start:end])
            at = end
            continue
        if classes[at] == 2:
            pieces.append(text[at : at + 1])
            at += 1
            continue
        punct_at = at + 1 if text[at] == " " and at + 1 < len(text) and classes[at + 1] == 0 else at
        if classes[punct_at] == 0:
            end = punct_at + 1
            while end < len(text) and classes[end] == 0:
                end += 1
            while end < len(text) and text[end] in "\r\n":
                end += 1
            pieces.append(text[start:end])
            at = end
            continue
        if classes[at] == 3:
            end = at + 1
            last_newline = at if text[at] in "\r\n" else -1
            while end < len(text) and classes[end] == 3:
                if text[end] in "\r\n":
                    last_newline = end
                end += 1
            if last_newline >= at:
                pieces.append(text[at : last_newline + 1])
                at = last_newline + 1
            else:
                emitted = end - 1 if end < len(text) and end - at > 1 else end
                pieces.append(text[at:emitted])
                at = emitted
            continue
        pieces.append(text[at : at + 1])
        at += 1
    return pieces


def encode_data(
    text: str,
    tokens: list[str],
    types: list[int],
    merges: list[str],
    parse_control: bool = True,
) -> list[int]:
    token_ids = {token: index for index, token in enumerate(tokens)}
    ranks = {tuple(merge.split(" ", 1)): rank for rank, merge in enumerate(merges)}
    candidates = []
    for index, (token, token_type) in enumerate(zip(tokens, types)):
        effective = 3 if token_type == 1 and token == "</s>" else token_type
        if effective == 4 or parse_control and effective in (2, 3):
            candidates.append((token, index))

    result: list[int] = []

    def encode_raw(raw: str) -> None:
        for piece in qwen_pieces(raw):
            symbols = [byte_spelling(value) for value in piece.encode("utf-8")]
            while len(symbols) > 1:
                choices = [
                    (ranks[(symbols[index], symbols[index + 1])], index)
                    for index in range(len(symbols) - 1)
                    if (symbols[index], symbols[index + 1]) in ranks
                ]
                if not choices:
                    break
                _, index = min(choices)
                symbols[index : index + 2] = [symbols[index] + symbols[index + 1]]
            result.extend(token_ids[symbol] for symbol in symbols)

    raw_start = 0
    at = 0
    while at < len(text):
        matches = [(candidate, token_id) for candidate, token_id in candidates if text.startswith(candidate, at)]
        if matches:
            candidate, token_id = max(matches, key=lambda row: len(row[0].encode("utf-8")))
            encode_raw(text[raw_start:at])
            result.append(token_id)
            at += len(candidate)
            raw_start = at
        else:
            at += 1
    encode_raw(text[raw_start:])
    return result


def encode(text: str, parse_control: bool = True) -> list[int]:
    tokens, types, merges = fixture_data()
    return encode_data(text, tokens, types, merges, parse_control)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1].startswith("-"):
        print("usage: tokenizer_fixture.py OUTPUT_DIR", file=sys.stderr)
        return 2
    output = Path(argv[1])
    output.mkdir(parents=True, exist_ok=True)
    manifest = build(output)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
