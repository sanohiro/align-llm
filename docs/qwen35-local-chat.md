# Local Qwen3.5 chat on Apple M1

This is the tested text-only, loopback OpenAI-compatible route for Qwen3.5-2B
Q4_0. It supports `GET /v1/models` and `POST /v1/chat/completions`, including
`stream: true`. The qualified host is an Apple M1 with 16 GiB of unified memory.
CPU, CUDA, tools, images, audio, and remote binding are outside this route.

## Prepare the model and Metal backend

Download `Qwen3.5-2B-Q4_0.gguf` from
[the selected Unsloth revision](https://huggingface.co/unsloth/Qwen3.5-2B-GGUF/blob/f6d5376be1edb4d416d56da11e5397a961aca8ae/Qwen3.5-2B-Q4_0.gguf)
to a directory outside Git. Its SHA-256 must be
`cd70221bebaee0503e0f6717e174250cd7825aa88438b3aabec9ad55731d9bb1`.
Set these paths to your own absolute locations:

```sh
MODEL=/absolute/path/Qwen3.5-2B-Q4_0.gguf
LLAMA_CPP=/absolute/path/llama.cpp
METAL_OUTPUT=/absolute/path/metal-output
WORK=/absolute/path/qwen35-2b-serving
mkdir -p "$WORK"
shasum -a 256 "$MODEL"
```

The `LLAMA_CPP` checkout must be clean and at the commit in `.llama-revision`.
Create a new backend output directory once, or reuse a bundle already built from
that pin:

```sh
scripts/gpu_backend_recipe.py --backend metal --source "$LLAMA_CPP" --output "$METAL_OUTPUT"
BUNDLE="$METAL_OUTPUT/bundle"
```

The recipe refuses an occupied output path. To reuse an existing bundle, set
`BUNDLE` directly to its `bundle/` directory. The backend build details are in
[Align development notes](align-development.md#provider-development).

## Build the server and prepare the source-bound files

From the repository root, build with the pinned Align compiler and the same
ggml headers and Metal libraries. On Homebrew macOS, OpenSSL may need the
shown linker search path:

```sh
ALIGN_LLM_GGML_INCLUDE="$LLAMA_CPP/ggml/include" \
ALIGN_LLM_GGML_LIB="$BUNDLE" \
LIBRARY_PATH=/opt/homebrew/lib:/opt/homebrew/opt/openssl@3/lib \
gmake build

DYLD_LIBRARY_PATH="$BUNDLE" ./main --model-ir "$MODEL" "$WORK/model-ir.json"
DYLD_LIBRARY_PATH="$BUNDLE" ./main --pack "$MODEL" "$WORK/model.alignpack" "$WORK/pack-report.json"
DYLD_LIBRARY_PATH="$BUNDLE" ./main --pack-verify "$MODEL" "$WORK/model.alignpack" "$WORK/pack-verify.json"
```

The options below are the tested resident Metal setup for the qualified host.
Use absolute paths; the server verifies the GGUF, Model IR, pack, and backend
before opening the listener.

```sh
cat > "$WORK/runtime-options.json" <<EOF
{"schema_version":1,"backend":"metal","device":"MTL0","backend_bundle":"$BUNDLE","placement":"resident","host_budget_bytes":2147483648,"device_budget_bytes":4294967296,"prefetch":"off"}
EOF

DYLD_LIBRARY_PATH="$BUNDLE" ./main --serve-openai \
  "$MODEL" "$WORK/model.alignpack" "$WORK/model-ir.json" \
  "$WORK/runtime-options.json" 0 qwen35-2b 8080
```

Keep the server running and use a second terminal for requests:

```sh
curl http://127.0.0.1:8080/v1/models
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen35-2b","messages":[{"role":"user","content":"Name one Python data structure."}],"max_tokens":32,"temperature":0}'
curl -N http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen35-2b","messages":[{"role":"user","content":"Count from 1 to 10."}],"max_tokens":32,"temperature":0,"stream":true}'
```

Set an OpenAI-compatible client's base URL to `http://127.0.0.1:8080/v1`
and its model id to `qwen35-2b`. Requests are serialized in this first
server. The supported request fields and error behavior are recorded in the
[local serving contract](specs/openai-local-serving.md).
