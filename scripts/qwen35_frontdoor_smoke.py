#!/usr/bin/env python3
"""Independent small qwen35 GGUF oracle for the Model IR and pack CLI."""

import json
import subprocess
import tempfile
from pathlib import Path

from gguf_fixture import Array, Container, INT32, STRING, Kv, Tensor, f32v, i32v, nbytes_of, strv, u32v


ROOT = Path(__file__).resolve().parent.parent
MAIN = ROOT / "main"


def fixture(*, missing=None, wrong_shape=False, pre="qwen35"):
    # Independently transcribed from the GGUF's 3:1 recurrent/full-attention layout.
    embd, head, kv, head_dim, ff = 64, 2, 1, 16, 128
    state, groups, rank, inner, conv, vocab = 8, 8, 8, 64, 4, 64
    qkv = 2 * state * groups + inner
    metadata = [
        ("general.architecture", strv("qwen35")),
        ("qwen35.block_count", u32v(4)),
        ("qwen35.context_length", u32v(512)),
        ("qwen35.embedding_length", u32v(embd)),
        ("qwen35.feed_forward_length", u32v(ff)),
        ("qwen35.attention.head_count", u32v(head)),
        ("qwen35.attention.head_count_kv", u32v(kv)),
        ("qwen35.attention.key_length", u32v(head_dim)),
        ("qwen35.attention.value_length", u32v(head_dim)),
        ("qwen35.attention.layer_norm_rms_epsilon", f32v(1e-6)),
        ("qwen35.rope.freq_base", f32v(10000000.0)),
        ("qwen35.rope.dimension_count", u32v(16)),
        ("qwen35.rope.dimension_sections", Array(INT32, [i32v(2), i32v(2), i32v(4), i32v(0)])),
        ("qwen35.ssm.conv_kernel", u32v(conv)),
        ("qwen35.ssm.state_size", u32v(state)),
        ("qwen35.ssm.group_count", u32v(groups)),
        ("qwen35.ssm.time_step_rank", u32v(rank)),
        ("qwen35.ssm.inner_size", u32v(inner)),
        ("qwen35.full_attention_interval", u32v(4)),
        ("tokenizer.ggml.pre", strv(pre)),
        ("tokenizer.ggml.model", strv("gpt2")),
        ("tokenizer.ggml.tokens", Array(STRING, [strv(f"t{i}") for i in range(vocab)])),
        ("tokenizer.ggml.token_type", Array(INT32, [i32v(1) for _ in range(vocab)])),
        ("tokenizer.ggml.merges", Array(STRING, [strv("t0 t1")])),
    ]
    kvs = [Kv(key, value) for key, value in metadata if key != missing]
    weights = [("token_embd.weight", [embd, vocab])]
    for layer in range(4):
        prefix = f"blk.{layer}."
        weights.append((prefix + "attn_norm.weight", [embd]))
        if layer == 3:
            weights += [
                (prefix + "attn_q.weight", [embd, head * head_dim * 2]),
                (prefix + "attn_q_norm.weight", [head_dim]),
                (prefix + "attn_k.weight", [embd, kv * head_dim]),
                (prefix + "attn_k_norm.weight", [head_dim]),
                (prefix + "attn_v.weight", [embd, kv * head_dim]),
                (prefix + "attn_output.weight", [head * head_dim, embd]),
            ]
        else:
            weights += [
                (prefix + "attn_qkv.weight", [embd, qkv]),
                (prefix + "attn_gate.weight", [embd, inner]),
                (prefix + "ssm_conv1d.weight", [conv, qkv]),
                (prefix + "ssm_dt.bias", [rank]),
                (prefix + "ssm_a", [rank]),
                (prefix + "ssm_beta.weight", [embd, rank]),
                (prefix + "ssm_alpha.weight", [embd, rank]),
                (prefix + "ssm_norm.weight", [state]),
                (prefix + "ssm_out.weight", [inner, embd]),
            ]
        weights += [
            (prefix + "post_attention_norm.weight", [embd]),
            (prefix + "ffn_gate.weight", [embd, ff]),
            (prefix + "ffn_up.weight", [embd, ff]),
            (prefix + "ffn_down.weight", [ff, embd]),
        ]
    weights.append(("output_norm.weight", [embd]))
    if wrong_shape:
        at = next(i for i, (name, _) in enumerate(weights) if name == "blk.0.ssm_out.weight")
        weights[at] = (weights[at][0], [inner, embd // 2])
    offset = 0
    tensors = []
    for name, dims in weights:
        tensors.append(Tensor(name, dims, 0, offset))
        offset += nbytes_of(dims, 0)
    return Container(kvs, tensors, data_len=offset)


def run(*args):
    return subprocess.run([str(MAIN), *map(str, args)], capture_output=True, text=True)


def check():
    with tempfile.TemporaryDirectory(prefix="qwen35-frontdoor-") as tmp:
        work = Path(tmp)
        model = work / "qwen35.gguf"
        model.write_bytes(fixture().bytes)
        ir_path = work / "model-ir.json"
        result = run("--model-ir", model, ir_path)
        assert result.returncode == 0, result.stderr
        ir = json.loads(ir_path.read_text())
        assert ir["status"] == "ok" and ir["model"]["arch"] == "qwen35"
        assert list(ir["model"]) == [
            "arch", "n_layer", "n_embd", "n_head", "n_head_kv", "head_dim", "n_ff",
            "full_attention_interval", "ssm_conv_kernel", "ssm_state_size", "ssm_group_count",
            "ssm_time_step_rank", "ssm_inner_size", "n_vocab", "n_expert", "context_length",
            "rms_eps", "rms_eps_bits", "rope",
        ]
        assert ir["model"]["rope"]["type"] == 40
        assert ir["coverage"]["tensor_count"] == 55
        assert ir["coverage"]["assigned_tensor_count"] == 55
        assert ir["coverage"]["size_sum_ok"] is True
        assert len(ir["blocks"]) == 10
        assert [b["tensor_count"] for b in ir["blocks"][:4]] == [1, 11, 3, 11]
        direct = run("--model-ir", model)
        assert direct.returncode == 0 and json.loads(direct.stdout) == ir

        pack = work / "model.alignpack"
        packed = run("--pack", model, pack)
        assert packed.returncode == 0, packed.stderr
        assert json.loads(packed.stdout)["status"] == "ok"
        verified = run("--pack-verify", model, pack)
        assert verified.returncode == 0, verified.stderr
        assert json.loads(verified.stdout)["status"] == "ok"

        negatives = [
            ("missing", fixture(missing="qwen35.ssm.state_size"), "R1_MISSING_KEY"),
            ("vocab", fixture(missing="tokenizer.ggml.tokens"), "R1_MISSING_KEY"),
            ("shape", fixture(wrong_shape=True), "R1_TENSOR_SHAPE_UNEXPECTED"),
            ("pre", fixture(pre="qwen2"), "R1_KEY_VALUE_IMPLAUSIBLE"),
        ]
        for name, bad_model, code in negatives:
            source = work / f"{name}.gguf"
            source.write_bytes(bad_model.bytes)
            failed = work / f"{name}.alignpack"
            response = run("--pack", source, failed)
            assert response.returncode != 0, name
            assert json.loads(response.stdout)["error_code"] == code, (name, response.stdout)
            assert not failed.exists(), name
    print("qwen35 frontdoor smoke PASS: synthetic model IR, pack, verify, malformed key/vocab/shape/pre")


if __name__ == "__main__":
    check()
