#ifndef ALIGN_NATIVE_METAL_STATE_COPY_H
#define ALIGN_NATIVE_METAL_STATE_COPY_H

#include <stddef.h>
#include <stdint.h>

struct align_native_metal_copy {
    uint64_t source_offset;
    uint64_t destination_offset;
    uint32_t elements;
    uint32_t reserved;
};

#ifdef __cplusplus
extern "C" {
#endif

void *align_native_metal_copy_open(const char *selected_device_description);
int align_native_metal_copy_submit(void *context,
        void *source_base, size_t source_size,
        void *destination_base, size_t destination_size,
        const struct align_native_metal_copy *copies, size_t count);
int align_native_metal_copy_wait(void *context);
int align_native_metal_copy_reset_views(void *context);
void align_native_metal_copy_close(void *context);

#ifdef __cplusplus
}
#endif

#endif
