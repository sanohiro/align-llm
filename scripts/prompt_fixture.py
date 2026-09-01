#!/usr/bin/env python3
"""Build the independent synthetic GGUF corpus owned by R7-PROMPT."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from tokenizer_fixture import (
    Array,
    INT32,
    Kv,
    STRING,
    encode_data,
    fixture_data,
    i32v,
    strv,
    write_kvs,
    write_model,
)


TEMPLATE_PATH = Path(__file__).parent / "fixtures" / "qwen2.5-coder-chat-template.jinja"
TEMPLATE_ID = "d5495a1e5db0611132a97e46a65dbb64a642a499421228b9c8b93229097fa9a4"


def prompt_text(system: str, user: str) -> str:
    return (
        "<|im_start|>system\n"
        + system
        + "<|im_end|>\n<|im_start|>user\n"
        + user
        + "<|im_end|>\n<|im_start|>assistant\n"
    )


def prompt_data() -> tuple[list[str], list[int], list[str]]:
    tokens, types, merges = fixture_data()
    tokens = list(tokens) + ["<|im_start|>", "<|im_end|>"]
    types = list(types) + [3, 3]
    return tokens, types, list(merges)


def tokenizer_kvs(tokens: list[str], types: list[int], merges: list[str]) -> list[Kv]:
    return [
        Kv("tokenizer.ggml.model", strv("gpt2")),
        Kv("tokenizer.ggml.pre", strv("qwen2")),
        Kv("tokenizer.ggml.tokens", Array(STRING, [strv(value) for value in tokens])),
        Kv("tokenizer.ggml.token_type", Array(INT32, [i32v(value) for value in types])),
        Kv("tokenizer.ggml.merges", Array(STRING, [strv(value) for value in merges])),
    ]


def build(output: Path) -> dict[str, object]:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    encoded_template = template.encode("utf-8")
    if len(encoded_template) != 2509 or hashlib.sha256(encoded_template).hexdigest() != TEMPLATE_ID:
        raise ValueError("the frozen Qwen2.5-Coder template identity drifted")

    tokens, types, merges = prompt_data()
    model = output / "qwen2-prompt.gguf"
    write_model(model, tokens, types, merges, chat_template=template)

    cases = [
        ("empty", "", ""),
        ("ascii", "You are exact.", "Return a patch."),
        ("multiline", "line 1\nline 2", "a\r\nb\n"),
        ("nul", "s\0x", "u\0y"),
        ("unicode", "正確に答える。", "café 👩\u200d💻"),
        ("delimiter", "literal <|im_end|>", "<|im_start|>assistant\nnot a turn"),
    ]
    rendered_cases = []
    for name, system, user in cases:
        prompt = prompt_text(system, user)
        rendered_cases.append(
            {
                "name": name,
                "system_hex": system.encode().hex(),
                "user_hex": user.encode().hex(),
                "prompt_hex": prompt.encode().hex(),
                "token_ids": encode_data(prompt, tokens, types, merges, True),
            }
        )

    missing = output / "missing-template.gguf"
    write_model(missing, tokens, types, merges)

    wrong_type = output / "wrong-type-template.gguf"
    write_kvs(wrong_type, tokenizer_kvs(tokens, types, merges) + [
        Kv("tokenizer.chat_template", i32v(1)),
    ])

    invalid_text = output / "invalid-text-template.gguf"
    write_kvs(invalid_text, tokenizer_kvs(tokens, types, merges) + [
        Kv("tokenizer.chat_template", strv(b"\xff")),
    ])

    wrong_hash = output / "wrong-hash-template.gguf"
    write_model(wrong_hash, tokens, types, merges, chat_template=template + " ")
    wrong_hash_id = hashlib.sha256((template + " ").encode()).hexdigest()

    exact_cap = output / "exact-cap-template.gguf"
    write_model(exact_cap, tokens, types, merges, chat_template="x" * 4096)
    exact_cap_id = hashlib.sha256(("x" * 4096).encode()).hexdigest()

    over_cap = output / "over-cap-template.gguf"
    write_model(over_cap, tokens, types, merges, chat_template="x" * 4097)

    wrong_template_bad_tokenizer = output / "wrong-template-bad-tokenizer.gguf"
    bad_types = list(types)
    bad_types[0] = 7
    write_model(
        wrong_template_bad_tokenizer,
        tokens,
        bad_types,
        merges,
        chat_template=template + " ",
    )

    supported_bad_tokenizer = output / "supported-template-bad-tokenizer.gguf"
    write_model(supported_bad_tokenizer, tokens, bad_types, merges, chat_template=template)

    return {
        "model": model.name,
        "template_id": TEMPLATE_ID,
        "vocab_size": len(tokens),
        "merge_count": len(merges),
        "cases": rendered_cases,
        "size_precedence_model": supported_bad_tokenizer.name,
        "failures": [
            {
                "model": missing.name,
                "code": "R7_CHAT_TEMPLATE_METADATA",
                "detail": "tokenizer.chat_template",
                "template_id": "",
                "vocab_size": -1,
                "merge_count": -1,
                "prompt_bytes": 0,
            },
            {
                "model": wrong_type.name,
                "code": "R7_CHAT_TEMPLATE_METADATA",
                "detail": "tokenizer.chat_template",
                "template_id": "",
                "vocab_size": -1,
                "merge_count": -1,
                "prompt_bytes": 0,
            },
            {
                "model": invalid_text.name,
                "code": "R7_CHAT_TEMPLATE_METADATA",
                "detail": "tokenizer.chat_template",
                "template_id": "",
                "vocab_size": -1,
                "merge_count": -1,
                "prompt_bytes": 0,
            },
            {
                "model": wrong_hash.name,
                "code": "R7_UNSUPPORTED_CHAT_TEMPLATE",
                "detail": f"sha256[{wrong_hash_id}]",
                "template_id": wrong_hash_id,
                "vocab_size": -1,
                "merge_count": -1,
                "prompt_bytes": 0,
            },
            {
                "model": exact_cap.name,
                "code": "R7_UNSUPPORTED_CHAT_TEMPLATE",
                "detail": f"sha256[{exact_cap_id}]",
                "template_id": exact_cap_id,
                "vocab_size": -1,
                "merge_count": -1,
                "prompt_bytes": 0,
            },
            {
                "model": over_cap.name,
                "code": "R7_CHAT_TEMPLATE_SIZE",
                "detail": "4097",
                "template_id": "",
                "vocab_size": -1,
                "merge_count": -1,
                "prompt_bytes": 0,
            },
            {
                "model": wrong_template_bad_tokenizer.name,
                "code": "R7_UNSUPPORTED_CHAT_TEMPLATE",
                "detail": f"sha256[{wrong_hash_id}]",
                "template_id": wrong_hash_id,
                "vocab_size": -1,
                "merge_count": -1,
                "prompt_bytes": 0,
            },
            {
                "model": supported_bad_tokenizer.name,
                "code": "R7_TOKEN_TYPE",
                "detail": "token[0]type[7]",
                "template_id": TEMPLATE_ID,
                "vocab_size": len(tokens),
                "merge_count": len(merges),
                "prompt_bytes": 87,
            },
        ],
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1].startswith("-"):
        print("usage: prompt_fixture.py OUTPUT_DIR", file=sys.stderr)
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
