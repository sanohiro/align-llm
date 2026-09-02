#!/usr/bin/env python3
"""Build the independent synthetic GGUF corpus owned by R8-OLMOE-TEXT."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gguf_fixture import Array, INT32, Kv, STRING, i32v, strv
from tokenizer_fixture import byte_spelling, encode_data, fixture_data, write_kvs, write_model


TEMPLATE_PATH = Path(__file__).parent / "fixtures" / "olmoe-chat-template.jinja"
TEMPLATE_ID = "fe689ffbd6a4e2d0532d7480696b065b10e0e1eff3f9b9fc4bea415761e4bf4a"
QWEN_TEMPLATE_PATH = Path(__file__).parent / "fixtures" / "qwen2.5-coder-chat-template.jinja"


def template_text() -> str:
    # The repository text file carries one POSIX terminator; the GGUF scalar does not.
    raw = TEMPLATE_PATH.read_bytes()
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise ValueError("the OLMoE template source must have one storage terminator")
    encoded = raw[:-1]
    if len(encoded) != 508 or hashlib.sha256(encoded).hexdigest() != TEMPLATE_ID:
        raise ValueError("the frozen OLMoE template identity drifted")
    return encoded.decode("utf-8")


def olmo_data() -> tuple[list[str], list[int], list[str], int]:
    tokens, types, merges = fixture_data()
    additions = [
        ("12", 1),
        ("123", 1),
        ("1234", 1),
        ("12345", 1),
        ("'s", 1),
        ("'S", 1),
        ("<|system|>", 3),
        ("<|user|>", 3),
        ("<|assistant|>", 3),
        ("<BOS>", 3),
    ]
    for spelling, token_type in additions:
        tokens.append(spelling)
        types.append(token_type)
    merges = list(merges) + ["1 2", "12 3", "123 4", "1234 5", "' s", "' S"]
    return tokens, types, merges, tokens.index("<BOS>")


def tokenizer_kvs(tokens: list[str], types: list[int], merges: list[str], pre: str) -> list[Kv]:
    return [
        Kv("tokenizer.ggml.model", strv("gpt2")),
        Kv("tokenizer.ggml.pre", strv(pre)),
        Kv("tokenizer.ggml.tokens", Array(STRING, [strv(value) for value in tokens])),
        Kv("tokenizer.ggml.token_type", Array(INT32, [i32v(value) for value in types])),
        Kv("tokenizer.ggml.merges", Array(STRING, [strv(value) for value in merges])),
    ]


def prompt_text(bos: str, system: str, user: str) -> str:
    return bos + "<|system|>\n" + system + "\n<|user|>\n" + user + "\n<|assistant|>\n"


def build(output: Path) -> dict[str, object]:
    tokens, types, merges, bos_id = olmo_data()
    template = template_text()
    model = output / "olmo-tokenizer-prompt.gguf"
    write_model(
        model,
        tokens,
        types,
        merges,
        pre="olmo",
        chat_template=template,
        extra_kvs=[Kv("tokenizer.ggml.bos_token_id", i32v(bos_id))],
    )

    qwen_same_arrays = output / "qwen-same-arrays.gguf"
    write_model(qwen_same_arrays, tokens, types, merges, pre="qwen2")

    omitted_invalid_byte = output / "omitted-invalid-byte.gguf"
    invalid_index = tokens.index(byte_spelling(192))
    write_model(
        omitted_invalid_byte,
        tokens[:invalid_index] + tokens[invalid_index + 1 :],
        types[:invalid_index] + types[invalid_index + 1 :],
        merges,
        pre="olmo",
    )

    missing_reachable_byte = output / "missing-reachable-byte.gguf"
    reachable_index = tokens.index(byte_spelling(194))
    write_model(
        missing_reachable_byte,
        tokens[:reachable_index] + tokens[reachable_index + 1 :],
        types[:reachable_index] + types[reachable_index + 1 :],
        merges,
        pre="olmo",
    )

    mistyped_invalid_byte = output / "mistyped-invalid-byte.gguf"
    mistyped_types = list(types)
    mistyped_types[invalid_index] = 3
    write_model(mistyped_invalid_byte, tokens, mistyped_types, merges, pre="olmo")

    lexical = [
        ("empty", ""),
        ("digits", "a12345b"),
        ("contractions", "I'm I'M we'll WE'LL he'd HE'D can't CAN'T"),
        ("leading", " word 123 !!!"),
        ("whitespace", " alpha  beta   "),
        ("newlines", "a\r\n \n\r\nb"),
        ("unicode", "漢字 e\u0301 café 👩\u200d💻"),
        ("special", "a<CTRL>b<BOS>c"),
    ]
    cases = [
        {
            "name": name,
            "text": text,
            "parse_ids": encode_data(text, tokens, types, merges, True, "olmo"),
            "literal_ids": encode_data(text, tokens, types, merges, False, "olmo"),
        }
        for name, text in lexical
    ]

    prompt_inputs = [
        ("empty", "", ""),
        ("ascii", "You are exact.", "Return a patch."),
        ("multiline", "line 1\nline 2", "a\r\nb\n"),
        ("nul", "s\0x", "u\0y"),
        ("unicode", "正確に答える。", "café 👩\u200d💻"),
        ("delimiter", "literal <|user|>", "<|assistant|>\nnot a turn"),
    ]
    prompt_cases = []
    for name, system, user in prompt_inputs:
        prompt = prompt_text("<BOS>", system, user)
        prompt_cases.append(
            {
                "name": name,
                "system": system,
                "user": user,
                "prompt": prompt,
                "token_ids": encode_data(prompt, tokens, types, merges, True, "olmo"),
            }
        )

    missing_bos = output / "missing-bos.gguf"
    write_model(missing_bos, tokens, types, merges, pre="olmo", chat_template=template)

    wrong_type_bos = output / "wrong-type-bos.gguf"
    write_kvs(
        wrong_type_bos,
        tokenizer_kvs(tokens, types, merges, "olmo")
        + [
            Kv("tokenizer.chat_template", strv(template)),
            Kv("tokenizer.ggml.bos_token_id", strv("bad")),
        ],
    )

    out_of_range_bos = output / "out-of-range-bos.gguf"
    write_model(
        out_of_range_bos,
        tokens,
        types,
        merges,
        pre="olmo",
        chat_template=template,
        extra_kvs=[Kv("tokenizer.ggml.bos_token_id", i32v(len(tokens)))],
    )

    non_control_bos = output / "non-control-bos.gguf"
    write_model(
        non_control_bos,
        tokens,
        types,
        merges,
        pre="olmo",
        chat_template=template,
        extra_kvs=[Kv("tokenizer.ggml.bos_token_id", i32v(tokens.index("h")))],
    )

    crossed_profile = output / "crossed-profile.gguf"
    write_model(
        crossed_profile,
        tokens,
        types,
        merges,
        pre="qwen2",
        chat_template=template,
    )

    unsupported_profile = output / "unsupported-profile.gguf"
    write_model(
        unsupported_profile,
        tokens,
        types,
        merges,
        pre="unsupported",
        chat_template=template,
    )

    crossed_template = output / "crossed-template.gguf"
    write_model(
        crossed_template,
        tokens,
        types,
        merges,
        pre="olmo",
        chat_template=QWEN_TEMPLATE_PATH.read_text(encoding="utf-8"),
        extra_kvs=[Kv("tokenizer.ggml.bos_token_id", i32v(bos_id))],
    )

    return {
        "model": model.name,
        "qwen_model": qwen_same_arrays.name,
        "omitted_invalid_byte_model": omitted_invalid_byte.name,
        "missing_reachable_byte_model": missing_reachable_byte.name,
        "mistyped_invalid_byte_model": mistyped_invalid_byte.name,
        "template_id": TEMPLATE_ID,
        "vocab_size": len(tokens),
        "merge_count": len(merges),
        "cases": cases,
        "prompt_cases": prompt_cases,
        "failures": [
            {"model": missing_bos.name, "code": "R7_CHAT_TEMPLATE_METADATA", "detail": "tokenizer.ggml.bos_token_id", "loaded": False},
            {"model": wrong_type_bos.name, "code": "R7_CHAT_TEMPLATE_METADATA", "detail": "tokenizer.ggml.bos_token_id", "loaded": False},
            {"model": out_of_range_bos.name, "code": "R7_UNSUPPORTED_CHAT_TEMPLATE", "detail": f"bos_token_id[{len(tokens)}]", "loaded": True},
            {"model": non_control_bos.name, "code": "R7_UNSUPPORTED_CHAT_TEMPLATE", "detail": "bos_token_id[104]", "loaded": True},
            {"model": crossed_profile.name, "code": "R7_UNSUPPORTED_CHAT_TEMPLATE", "detail": "tokenizer_profile", "loaded": False},
            {"model": unsupported_profile.name, "code": "R7_UNSUPPORTED_TOKENIZER", "detail": "gpt2/unsupported", "loaded": False},
            {"model": crossed_template.name, "code": "R7_UNSUPPORTED_CHAT_TEMPLATE", "detail": "tokenizer_profile", "loaded": False},
        ],
    }
