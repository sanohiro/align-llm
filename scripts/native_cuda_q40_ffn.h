#ifndef ALIGN_NATIVE_CUDA_Q40_FFN_H
#define ALIGN_NATIVE_CUDA_Q40_FFN_H

#include <stddef.h>
#define ALIGN_NATIVE_CUDA_Q40_FFN_DEVICE_BYTES 41984LL

#ifdef __cplusplus
extern "C" {
#endif

// Inputs are caller-owned device allocations. Outputs remain helper-owned until close.
// Only the screened Q4_0 single-row shape is admitted.
void *align_native_cuda_q40_ffn_open(int width, int hidden);
int align_native_cuda_q40_ffn_run(void *context, const void *gate, const void *up,
        const void *down, const float *input);
int align_native_cuda_q40_ffn_read(void *context, float *gated, size_t gated_count,
        float *output, size_t output_count);
void align_native_cuda_q40_ffn_close(void *context);
// Caller drains the borrowed stream before closing; these calls do not wait.
int align_native_cuda_q40_ffn_enqueue(void *context, const void *gate, const void *up,
        const void *down, const float *input, const float *residual, void *stream);
const float *align_native_cuda_q40_ffn_output(void *context);

#ifdef __cplusplus
}
#endif

#endif
