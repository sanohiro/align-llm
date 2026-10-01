#ifndef ALIGN_NATIVE_CUDA_Q40_FFN_H
#define ALIGN_NATIVE_CUDA_Q40_FFN_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Inputs are caller-owned device allocations. Outputs remain helper-owned until close.
// Only the screened Q4_0 single-row shape is admitted.
void *align_native_cuda_q40_ffn_open(int width, int hidden);
// Layout 0: raw 18-byte blocks. Layout 1: 16-byte payload plane, then half scales.
// Layout and borrowed pointer identities are immutable through close. Calls are serial.
void *align_native_cuda_q40_ffn_open_layout(int width, int hidden, int layout);
int align_native_cuda_q40_ffn_run(void *context, const void *gate, const void *up,
        const void *down, const float *input);
// Read requires a completed successful run. A refused run invalidates readiness;
// a CUDA execution/read failure poisons the context until close. Discard host
// outputs after a failed read (the first of two copies may already have finished).
int align_native_cuda_q40_ffn_read(void *context, float *gated, size_t gated_count,
        float *output, size_t output_count);
void align_native_cuda_q40_ffn_close(void *context);

#if defined(ALIGN_CUDA_Q4_TESTING)
// Diagnostic-only, single-use failure at the numbered CUDA acquisition/operation.
void align_native_cuda_q40_ffn_test_fail(int operation);
#endif

#ifdef __cplusplus
}
#endif

#endif
