The named `kv_plane.all_zero` residual is fixed at Align
`5c7af9e54108fbe3a7b3d698c96a6dbc2da3e9c3` (includes #1166/#1168):
the actual client unit now has a nonnegative borrowed length, no `llvm.smax`,
and a `<16 x i8>` vector loop.

A second borrowed-header path still misses Plan 69 I7. Adding an independent
one-element local allocation to the same scan disables cached view headers;
the fallback aggregate load then loses the length fact as well:

```align
module range_residual

pub fn plain(borrow view: slice<u8>) -> bool {
  mut at := 0
  loop {
    if at >= view.len() { break }
    if view.u8(at) as i64 != 0 { return false }
    at = at + 1
  }
  return true
}

pub fn allocated(borrow view: slice<u8>) -> bool {
  scratch := [0].to_array()
  mut at := 0
  loop {
    if at >= view.len() { break }
    if view.u8(at) as i64 != 0 { return false }
    at = at + 1
  }
  return scratch.len() == 1
}
```

Reproduce using the release compiler at the exact revision above:

```sh
alignc emit-llvm range-residual.align --stage raw --profile release --no-rt-lto
alignc emit-llvm range-residual.align --stage optimized --profile release --no-rt-lto
```

Observed on Apple M1, macOS 27.0, LLVM 22.1.8, baseline target:

| Function | Raw borrowed header | Optimized result |
| --- | --- | --- |
| `plain` | scalar length load with `!range !{i64 0, i64 -9223372036854775808}` | vector body; no `llvm.smax` |
| `allocated` | `load { ptr, i64 }, ptr %0` followed by `extractvalue`; no range fact | unannotated scalar length load; `llvm.smax.i64(len, 0)`; scalar scan |

The real `runtime_sampler.select_values` consumer also reloads its borrowed
`slice<f32>` length inside the vocabulary loop without `!range`.

At this revision, `ViewFactsPlan` explicitly says `!range` is independent of
its whole-body alias/caching gate. `load_view_part` implements that rule, but
`Rvalue::Load` at `crates/align_codegen_llvm/src/lib.rs:13885` falls back to an
aggregate load when `cached_view_header` is unavailable. Its later
`SliceLen(Value)` uses `extractvalue`, bypassing `load_view_part`. The
allocation fails the whole-body whitelist, exposing this path.

The demonstrated defect is the missing unconditional length invariant.
The absence of `noalias`/header caching is separately permitted by the
current conservative whole-body policy. Restoring the range fact alone is
not claimed to guarantee SIMD or to remove all sampler reloads.

Suggested acceptance: preserve the independently justified nonnegative length
fact on typed borrowed-header materialization even when caching is disabled,
cover the example above and the real sampler, and retain the existing
non-length-layout and foreign-provenance negative controls. No syntax, unsafe
assumption, or application spelling workaround is needed.
