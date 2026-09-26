# Qwen3.5 Metal mapped-weight trial

## Decision

Keep `ALIGN_LLM_MAPPED_WEIGHTS=1` as an opt-in experiment. The existing upload
path remains the default. The trial removes the application's copy of Alignpack
weights into a separate ggml-owned Metal allocation, but it does **not** close
the warm-request gap to pinned llama.cpp. Isolated startup improves; warm
prefill and decode results are small and mixed. No percentage threshold was
used. The complete unscreened samples are in
`../eval/benchmarks/qwen35-mapped-weights-metal-2026-09-27.json`.

This tests one causal hypothesis from `qwen35-decode-attribution.md`: pinned
llama.cpp maps weight pages, while Align previously read each pack tensor into
staging and uploaded it. The local 2B Alignpack is 1,621,209,088 bytes with
64-byte member alignment. A read-only `mmap` of that actual file was accepted by
the M1 Metal `newBufferWithBytesNoCopy` path before runtime integration. This
does not imply a speed or physical-memory gain.

## Execution boundary

Align parses the model and pack, chooses the session mode, verifies pack
identity, builds the tensor plan, admits the full mapped file extent, and owns
the session and generation loop. The thin C shim opens the selected file,
checks its size, maps it, asks ggml's device to wrap the host address, and
places each tensor at Align's validated pack offset. It closes the descriptor
after mapping. Session teardown synchronizes the backend, frees the ggml
buffer, then unmaps. The mapped path does not call the weight-upload ABI.
The existing ggml backend still runs all model graphs and kernels; no new
independent inference engine or Python product path was added. The default
upload path and all other model paths remain available.

The opt-in path assumes a stable local pack. Absolute and relative pack paths
accepted by the existing provider work in both modes. The Align validator and the C
mapper open the same path separately. Concurrent replacement between those
opens, or truncation after mmap, needs a same-descriptor validation or an
immutable-pack policy before production adoption. The current upload path also
does not hash every payload byte against concurrent mutation, but mmap adds a
retained-file lifetime. The new experiment refuses use with synchronous upload
mode, invalid environment values, misaligned or out-of-range tensor locations,
and a changed file extent. No mapped mode is enabled by default.

One comprehensive host-native review found that the first candidate rejected
relative pack paths even though the existing provider accepts them. The C
opener now preserves that input, and a real 2B relative-path request passes.
The review repair only removed a pre-open refusal; absolute-path execution used
by the measurements is unchanged. The receipt binds both the measured and the
final shim hashes.

## Correctness

The real 2B and 0.8B Q4_0 generation owners passed with mapped weights:
short, 200- and 330-token prompts, six requests in a retained session,
invalid-request recovery, and the pinned llama.cpp greedy output. The 2B
HTTP/SSE owner passed output parity, refusal, disconnect recovery and restart.
The 2B default-off generation owner also passed after the change.

An independent readback interposer captured three full-vocabulary outputs for
the same 2B request in both modes. All 744,960 F32 values are **bit identical**
(`max_abs=0`, versus the predeclared 0.01 bound), including argmax. A separate
state interposer compared 258 records across three complete graphs, including
all resident KV and recurrent planes; every record matches exactly. These
captures were excluded from performance runs. Raw captures and logs are in
the resolved Git common directory under
`diagnostics/q35-mapped-2026-09-27/`; no weights are committed.

## Performance

All 2B comparisons used the same GGUF, Alignpack, model IR, bundle, binary,
Q4_0 precision, prompt IDs and generation lengths. Native SwiGLU and the
single-row FFN experiment were off, chunk width was 128, final-prefill output
elision was on, and synchronous weight upload was off. Five alternating pairs
were retained for each condition. The worker trial used separate process
startups, two warm requests per Align arm, and pinned llama.cpp revision
`bb4caa7540188872173c44d161602d9271386413`. Phase clocks cover
synchronized graph execution, not individual shaders. The HTTP/SSE trial used
two simultaneously retained Align servers, two warmups and five alternating
pairs per mode. Its client and output conditions are identical across OFF/ON.

| Prompt / output | Worker OFF / mapped median request | Mapped vs llama median request | Worker OFF / mapped prefill | Worker OFF / mapped decode | HTTP paired mapped change | SSE paired mapped change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 64 / 16 | 570.4 / 569.3 ms | 569.3 / 545.5 ms | 125.6 / 124.5 ms | 429.7 / 429.9 ms | −1.10%, 0/5 faster | −0.14%, 2/5 faster |
| 200 / 32 | 1288.1 / 1289.6 ms | 1289.6 / 1253.3 ms | 383.1 / 382.3 ms | 878.7 / 877.3 ms | +0.17%, 3/5 faster | −0.25%, 1/5 faster |
| 330 / 64 | 2440.0 / 2428.9 ms | 2428.9 / 2347.8 ms | 598.9 / 597.7 ms | 1795.7 / 1784.7 ms | +0.04%, 3/5 faster | +0.07%, 3/5 faster |
| 1536 / 1 | N/A | N/A | N/A | N/A | +0.04%, 3/5 faster | −0.01%, 2/5 faster |

Percentages in the last two columns are medians of paired request changes,
positive when mapped is faster. The worker's 330/64 paired request improvement
is 0.42% (4/5 faster), while both HTTP/SSE changes there are near zero. The
worker's 200/32 mapped decode median changes by only 1.4 ms over 31 decode
steps. These samples do not establish a repeatable warm inference gain.
The pinned reference remains faster in the worker campaign by 2.9–4.4% on
median request times. Its native driver and Align's retained session protocol
have different host boundaries; the phase values and same-binary HTTP/SSE are
more useful for diagnosing this specific storage change than treating those
request medians as identical API endpoints.

Isolated worker construction-to-ready medians fell from 0.995 to 0.609 s,
0.986 to 0.546 s, and 1.020 to 0.620 s for the three conditions; all five
pairs in each condition favored mapping. The two-server HTTP/SSE setup instead
reported 1.104 s OFF and 1.237 s ON. That setup starts OFF first and leaves
both large resident sessions alive, so it is a different cache and memory
condition. Startup is promising in isolated processes but not a universal
claim. The old path's repeated pack reads and uploads have been removed in
source; no isolated file-load clock was separately captured.

A sequential warm 200/32 process probe reported 181,088 KiB RSS OFF and
145,328 KiB ON. `vmmap` showed a much larger mapped-file virtual region ON,
but both reported about 147 MiB peak process physical footprint. Those OS
figures exclude or account differently for GPU allocations and cannot prove a
whole-system physical-memory saving. The exact Metal buffer ownership is
verified by construction and cleanup, not inferred from RSS alone.

## Next investigation

The dominant Q4/Q5/Q6, attention and recurrent Metal launch signatures match
llama.cpp, and replacing weight storage produced no useful decode change.
Next, measure command-buffer boundaries and host graph preparation/scheduling
on the same 200/32 request with matched endpoints. If that still points to
device time, test a larger fused gate/up/activation/down segment or a new Q6_K
work mapping against the existing exact-logit/state oracle. Do not repeat the
previous paired-load Q6_K kernel: its real-weight probe showed no stable gain.
The mapped path can be reconsidered for startup or memory after fixing its
file identity/lifetime contract and obtaining a direct physical-memory result.

The mapped tensor-placement code is driven by shape, type, alignment and
pack offsets, so a different admitted Qwen size can reuse it. Its model
geometry, expected tensor roles and request qualification still need their own
checks. Gemma needs an architecture-specific semantic model admission for its
normalization, attention, position and activation behavior before this storage
mechanism can be reused. CUDA host-pointer capability and lifecycle remain
unmeasured; the CPU path is outside this Metal trial.
