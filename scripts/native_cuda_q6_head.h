#ifndef ALIGN_NATIVE_CUDA_Q6_HEAD_H
#define ALIGN_NATIVE_CUDA_Q6_HEAD_H

#include <stddef.h>
#include <stdint.h>

/* Output, Q8_1 input, 970 greedy partials and result; included in admission. */
#define ALIGN_NATIVE_CUDA_Q6_HEAD_DEVICE_BYTES 1003352LL

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

#ifdef __cplusplus
}
#endif

#endif
