#!/usr/bin/env python3
"""Build tiny F32 OLMoE models for the cache-backed provider owner."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from gguf_fixture import Array, INT32, OlmoeModel, STRING, i32v, strv
from gguf_fixture import OLMOE_GLOBAL_ROLES, OLMOE_LAYER_ROLES
from layer_forward_fixture import (
    MOE_DENSE_ROLES,
    MOE_EXPERT_ROLES,
    moe_model_forward,
    moe_model_head_tensor,
    moe_tensor,
)
from olmoe_text_fixture import olmo_data, prompt_text, template_text
from tokenizer_fixture import encode_data


SYSTEM = "You are a coding assistant. Return a concise patch-oriented answer."
USER = "x"


def build(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    tokens, token_types, merges, bos_id = olmo_data()
    geometry = {
        "arch": "olmoe",
        "n_layer": 2,
        "n_embd": 16,
        "n_head": 2,
        "n_head_kv": 2,
        "head_dim": 8,
        "n_ff": 32,
        "n_ff_exp": 32,
        "n_vocab": len(tokens),
        "n_expert": 4,
        "n_expert_used": 2,
        "context_length": 256,
        "rms_eps": 1e-05,
        "rope_freq_base": 10000.0,
        "rope_dim_count": 8,
        "rope_type": 2,
    }
    p = {
        "n_layer": geometry["n_layer"],
        "n_embd": geometry["n_embd"],
        "n_head": geometry["n_head"],
        "n_head_kv": geometry["n_head_kv"],
        "n_ff": geometry["n_ff"],
        "n_expert": geometry["n_expert"],
        "n_expert_used": geometry["n_expert_used"],
        "n_vocab": geometry["n_vocab"],
        "context_length": geometry["context_length"],
    }
    all_f32 = {role: 0 for role in OLMOE_GLOBAL_ROLES + OLMOE_LAYER_ROLES}
    prompt_ids = encode_data(
        prompt_text(tokens[bos_id], SYSTEM, USER), tokens, token_types, merges, True, "olmo"
    )
    width = len(prompt_ids) + 2
    embed = moe_tensor("token_embd", -1, geometry)
    layers = [
        {
            role: moe_tensor(role, layer, geometry)
            for role, _, _kind in MOE_DENSE_ROLES
            if role != "token_embd"
        }
        for layer in range(geometry["n_layer"])
    ]
    experts = [
        {
            role: [
                moe_tensor(role, layer, geometry, expert=expert)
                for expert in range(geometry["n_expert"])
            ]
            for role, _role_id in MOE_EXPERT_ROLES
        }
        for layer in range(geometry["n_layer"])
    ]
    head = {
        "output_norm": moe_model_head_tensor("output_norm", geometry),
        "output": moe_model_head_tensor("output", geometry),
    }
    _records, _routing, prefill_logits = moe_model_forward(
        embed, layers, experts, head, geometry, prompt_ids, width
    )
    first_id = max(range(prefill_logits.count()), key=lambda index: prefill_logits.data[index])
    # The hosted owner only needs the prefill and first decode boundary; the forced engine checks
    # that this exact F32 model is executable while EOG variants distinguish pre-graph stopping.

    tokenizer_rows = [
        ("tokenizer.ggml.model", strv("gpt2")),
        ("tokenizer.ggml.pre", strv("olmo")),
        ("tokenizer.ggml.token_type", Array(INT32, [i32v(value) for value in token_types])),
        ("tokenizer.ggml.merges", Array(STRING, [strv(value) for value in merges])),
        ("tokenizer.ggml.bos_token_id", i32v(bos_id)),
        ("tokenizer.chat_template", strv(template_text())),
    ]

    def write_model(name: str, eos_id: int) -> Path:
        model = OlmoeModel(
            p=p,
            types=all_f32,
            overrides={
                "tokenizer.ggml.tokens": Array(STRING, [strv(value) for value in tokens])
            },
            extra=tokenizer_rows + [("tokenizer.ggml.eos_token_id", i32v(eos_id))],
        )
        raw = bytearray(model.bytes)
        for index, (role, layer, _name, _dims, _type_id) in enumerate(model.entries):
            if role in ("ffn_gate_exps", "ffn_up_exps", "ffn_down_exps"):
                values = []
                for expert in range(geometry["n_expert"]):
                    values.extend(moe_tensor(role, layer, geometry, expert=expert).data)
            elif role in ("output_norm", "output"):
                values = moe_model_head_tensor(role, geometry).data
            else:
                values = moe_tensor(role, -1 if layer is None else layer, geometry).data
            payload = struct.pack("<%df" % len(values), *values)
            if len(payload) != model.sizes[index]:
                raise ValueError((role, layer, len(payload), model.sizes[index]))
            start = model.container.data_offset + model.offsets[index]
            raw[start : start + len(payload)] = payload
        path = output / name
        path.write_bytes(raw)
        return path

    ordinary_eog = tokens.index("</s>")
    if first_id == ordinary_eog:
        raise ValueError("synthetic prefill unexpectedly selected the ordinary EOG")
    model = write_model("runtime-olmoe.gguf", ordinary_eog)
    immediate = write_model("runtime-olmoe-immediate-eog.gguf", first_id)
    # Seed 11 selects byte-token ids 56 (`8`) then 50 (`2`) on this exact fixture. Separate EOG
    # variants prove that stopping follows the selected chain rather than the diagnostic argmax.
    sampled_seed = 11
    sampled_first_id = 56
    sampled_second_id = 50
    if tokens[sampled_first_id] != "8" or tokens[sampled_second_id] != "2":
        raise ValueError("sampled byte-token identities drifted")
    sampled_immediate = write_model("runtime-olmoe-sampled-immediate-eog.gguf", sampled_first_id)
    sampled_after_one = write_model("runtime-olmoe-sampled-after-one-eog.gguf", sampled_second_id)
    manifest = {
        "model": model.name,
        "immediate_eog_model": immediate.name,
        "sampled_immediate_eog_model": sampled_immediate.name,
        "sampled_after_one_eog_model": sampled_after_one.name,
        "first_id": first_id,
        "ordinary_eog_id": ordinary_eog,
        "sampled_seed": sampled_seed,
        "sampled_first_id": sampled_first_id,
        "sampled_second_id": sampled_second_id,
        "prompt_tokens": len(prompt_ids),
        "cache_budget_bytes": 65536,
    }
    (output / "olmoe-runtime-manifest.json").write_text(
        json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1].startswith("-"):
        sys.stderr.write("usage: olmoe_provider_fixture.py OUTDIR\n")
        return 2
    build(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
