#!/usr/bin/env python3
"""Build the self-contained dense Qwen fixture owned by R7-RUNTIME-PROVIDER.

The model combines the independent GGUF writer and tokenizer vocabulary with the deterministic
F32 weights used by the hosted whole-model/decode smoke.  The runtime owner can therefore exercise
the real GGUF -> model-IR -> alignpack -> resident provider path without a downloaded model,
llama.cpp, or a network service.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from gguf_fixture import Array, INT32, Kv, STRING, i32v, strv
from gguf_fixture import QWEN_GLOBAL_ROLES, QWEN_LAYER_ROLES, QwenModel
from layer_forward_fixture import GEOMETRY, model_decode, model_forward, model_tensor
from prompt_fixture import prompt_text
from tokenizer_fixture import encode_data, fixture_data


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts" / "fixtures" / "qwen2.5-coder-chat-template.jinja"
SYSTEM = "You are a coding assistant. Return a concise patch-oriented answer."
USER = "x"


def build(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    tokens, types, merges = fixture_data()
    geometry = dict(GEOMETRY)
    # F32 GGUF tensors are placed contiguously and every tensor begins on the 32-byte container
    # alignment.  Widen the tiny hosted geometry so even the one-dimensional KV biases are 32 B.
    geometry["n_embd"] = 16
    geometry["head_dim"] = 8
    geometry["n_ff"] = 32
    geometry["rope_dim_count"] = 8
    geometry["n_vocab"] = len(tokens)
    geometry["context_length"] = 256
    p = {
        "n_layer": geometry["n_layer"],
        "n_embd": geometry["n_embd"],
        "n_head": geometry["n_head"],
        "n_head_kv": geometry["n_head_kv"],
        "n_ff": geometry["n_ff"],
        "n_vocab": geometry["n_vocab"],
        "context_length": geometry["context_length"],
    }
    all_f32 = {role: 0 for role in QWEN_GLOBAL_ROLES + QWEN_LAYER_ROLES}
    text_eos_id = tokens.index("</s>")

    prompt_ids = encode_data(prompt_text(SYSTEM, USER), tokens, types, merges, True)
    width = len(prompt_ids) + 2
    embed = model_tensor("token_embd", -1, geometry)
    layers = [
        {
            role: model_tensor(role, layer, geometry)
            for role in QWEN_LAYER_ROLES
        }
        for layer in range(geometry["n_layer"])
    ]
    head = {
        "output_norm": model_tensor("output_norm", -1, geometry),
        "output": model_tensor("output", -1, geometry),
    }
    planes: list[object] = []
    _, prefill_logits = model_forward(embed, layers, head, geometry, prompt_ids, width, planes)
    first_id = max(range(prefill_logits.count()), key=lambda i: prefill_logits.data[i])
    _, step_logits = model_decode(
        embed, layers, head, geometry, planes, first_id, len(prompt_ids), width
    )
    second_id = max(range(step_logits.count()), key=lambda i: step_logits.data[i])
    if len({text_eos_id, first_id, second_id}) != 3:
        raise ValueError((text_eos_id, first_id, second_id))

    def tokenizer_metadata(kvs: list[Kv], eos_id: int) -> list[Kv]:
        kept = [kv for kv in kvs if kv.key_raw != b"tokenizer.ggml.tokens"]
        kept.extend(
            [
                Kv("tokenizer.ggml.model", strv("gpt2")),
                Kv("tokenizer.ggml.pre", strv("qwen2")),
                Kv("tokenizer.ggml.tokens", Array(STRING, [strv(value) for value in tokens])),
                Kv("tokenizer.ggml.token_type", Array(INT32, [i32v(value) for value in types])),
                Kv("tokenizer.ggml.merges", Array(STRING, [strv(value) for value in merges])),
                Kv("tokenizer.ggml.eos_token_id", i32v(eos_id)),
                Kv("tokenizer.chat_template", strv(TEMPLATE.read_text(encoding="utf-8"))),
            ]
        )
        return kept

    def write_runtime_model(name: str, eos_id: int) -> Path:
        model = QwenModel(
            p=p,
            types=all_f32,
            kv_override=lambda kvs: tokenizer_metadata(kvs, eos_id),
        )
        raw = bytearray(model.bytes)
        for index, (role, layer, _name, _dims, _type_id) in enumerate(model.entries):
            tensor = model_tensor(role, -1 if layer is None else layer, geometry)
            payload = struct.pack("<%df" % len(tensor.data), *tensor.data)
            if len(payload) != model.sizes[index]:
                raise ValueError((role, layer, len(payload), model.sizes[index]))
            start = model.container.data_offset + model.offsets[index]
            raw[start : start + len(payload)] = payload
        path = output / name
        path.write_bytes(raw)
        return path

    model_path = write_runtime_model("runtime-qwen2.gguf", text_eos_id)
    immediate_path = write_runtime_model("runtime-qwen2-immediate-eog.gguf", first_id)
    after_one_path = write_runtime_model("runtime-qwen2-after-one-eog.gguf", second_id)
    manifest = {
        "model": model_path.name,
        "immediate_eog_model": immediate_path.name,
        "after_one_eog_model": after_one_path.name,
        "text_eos_id": text_eos_id,
        "first_id": first_id,
        "second_id": second_id,
        "prompt_tokens": len(prompt_ids),
        "vocab_size": len(tokens),
        "context_length": geometry["context_length"],
    }
    (output / "runtime-manifest.json").write_text(
        json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1].startswith("-"):
        sys.stderr.write("usage: runtime_provider_fixture.py OUTDIR\n")
        return 2
    build(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
