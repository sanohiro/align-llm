#ifndef ALIGN_NATIVE_CUDA_Q6_HEAD_H
#define ALIGN_NATIVE_CUDA_Q6_HEAD_H

#include <stddef.h>
#include <stdint.h>

/* Output, Q8_1 input, 970 greedy partials and result; included in admission. */
#define ALIGN_NATIVE_CUDA_Q6_HEAD_DEVICE_BYTES 1003352LL
#define ALIGN_NATIVE_CUDA_FFN_TAIL_DEVICE_BYTES 58368LL

#ifdef __cplusplus
extern "C" {
#endif

void *align_native_cuda_q6_head_open(int device_ordinal);
int align_native_cuda_q6_head_run(void *context, const void *weight, const void *input);
int align_native_cuda_q6_head_run_greedy(void *context, const void *weight, const void *input);
int align_native_cuda_q6_head_read(void *context, void *output, size_t bytes);
int align_native_cuda_q6_head_greedy(void *context, int64_t *token);
int align_native_cuda_q6_head_wait(void *context);
void align_native_cuda_q6_head_close(void *context);
int align_native_cuda_q6_tail_enable(void *context);
int align_native_cuda_q6_tail_reset(void *context, int kind);
int align_native_cuda_q6_tail_run(void *context, int kind, const void *weight,
    const float *input, const float *attention, const float *norm,
    const void *gate, const void *up, const void *down, const float *head_norm,
    float epsilon);

#ifdef __cplusplus
}
#endif

#endif
