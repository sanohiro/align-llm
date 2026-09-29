#ifndef ALIGN_NATIVE_CUDA_STATE_COPY_H
#define ALIGN_NATIVE_CUDA_STATE_COPY_H

#include <stddef.h>
#include <stdint.h>

struct align_native_cuda_copy {
    uint64_t source_offset;
    uint64_t destination_offset;
    uint64_t bytes;
};

#ifdef __cplusplus
extern "C" {
#endif

void *align_native_cuda_copy_open(int device_ordinal);
int align_native_cuda_copy_submit(void *context, void *source_base, size_t source_size,
        void *destination_base, size_t destination_size,
        const struct align_native_cuda_copy *copies, size_t count);
int align_native_cuda_copy_wait(void *context);
void align_native_cuda_copy_close(void *context);

#ifdef __cplusplus
}
#endif

#endif
