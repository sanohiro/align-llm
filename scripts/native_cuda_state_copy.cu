// Thin CUDA command boundary for Align-owned recurrent-state copy selection.
#include "native_cuda_state_copy.h"

#include <cuda_runtime.h>
#include <new>
#include <stdint.h>
#include <stdio.h>

struct CopyContext {
    cudaStream_t stream = nullptr;
    int device = -1;
    bool pending = false;
};

struct CopyBatch {
    align_native_cuda_copy entries[64];
};

__global__ void copy_batch_16(const char *source, char *destination, CopyBatch batch) {
    const align_native_cuda_copy copy = batch.entries[blockIdx.y];
    const size_t offset = (size_t(blockIdx.x) * blockDim.x + threadIdx.x) * sizeof(uint4);
    if (offset >= copy.bytes) return;
    const auto *from = reinterpret_cast<const uint4 *>(source + copy.source_offset + offset);
    auto *to = reinterpret_cast<uint4 *>(destination + copy.destination_offset + offset);
    *to = *from;
}

extern "C" void *align_native_cuda_copy_open(int device_ordinal) {
    int count = 0;
    if (device_ordinal != 0 || cudaGetDeviceCount(&count) != cudaSuccess || count != 1
        || cudaSetDevice(device_ordinal) != cudaSuccess) return nullptr;
    auto *context = new (std::nothrow) CopyContext;
    if (context == nullptr) return nullptr;
    context->device = device_ordinal;
    if (cudaStreamCreateWithFlags(&context->stream, cudaStreamNonBlocking) != cudaSuccess) {
        delete context;
        return nullptr;
    }
    return context;
}

extern "C" int align_native_cuda_copy_submit(void *opaque,
        void *source_base, size_t source_size, void *destination_base,
        size_t destination_size, const struct align_native_cuda_copy *copies, size_t count) {
    auto *context = static_cast<CopyContext *>(opaque);
    if (context == nullptr || context->stream == nullptr || context->pending
        || source_base == nullptr || destination_base == nullptr || copies == nullptr
        || count < 1 || count > 64) return 0;
    if (cudaSetDevice(context->device) != cudaSuccess) return 0;
    cudaPointerAttributes source_attribute{}, destination_attribute{};
    if (cudaPointerGetAttributes(&source_attribute, source_base) != cudaSuccess
        || cudaPointerGetAttributes(&destination_attribute, destination_base) != cudaSuccess
        || source_attribute.type != cudaMemoryTypeDevice
        || destination_attribute.type != cudaMemoryTypeDevice
        || source_attribute.device != context->device
        || destination_attribute.device != context->device) return 0;
    bool vectorized = count > 1;
    size_t maximum_bytes = 0;
    for (size_t i = 0; i < count; ++i) {
        const auto &copy = copies[i];
        if (copy.bytes == 0 || copy.source_offset > source_size
            || copy.bytes > source_size - copy.source_offset
            || copy.destination_offset > destination_size
            || copy.bytes > destination_size - copy.destination_offset) return 0;
        if (source_base == destination_base
            && copy.source_offset < copy.destination_offset + copy.bytes
            && copy.destination_offset < copy.source_offset + copy.bytes) return 0;
        for (size_t j = 0; j < i; ++j) {
            const auto &prior = copies[j];
            if (copy.destination_offset < prior.destination_offset + prior.bytes
                && prior.destination_offset < copy.destination_offset + copy.bytes) return 0;
            if (source_base == destination_base
                && ((copy.source_offset < prior.destination_offset + prior.bytes
                        && prior.destination_offset < copy.source_offset + copy.bytes)
                    || (prior.source_offset < copy.destination_offset + copy.bytes
                        && copy.destination_offset < prior.source_offset + prior.bytes))) return 0;
        }
        if ((copy.source_offset | copy.destination_offset | copy.bytes) % sizeof(uint4) != 0)
            vectorized = false;
        if (copy.bytes > maximum_bytes) maximum_bytes = copy.bytes;
    }
#if defined(ALIGN_NATIVE_CUDA_FORCE_SUBMIT_FAILURE)
    fprintf(stderr, "native_state_copy forced submit failure\n");
    return 0;
#endif
    if (vectorized && maximum_bytes >= 65536 && maximum_bytes <= (size_t(1) << 30)) {
        CopyBatch batch{};
        for (size_t i = 0; i < count; ++i) batch.entries[i] = copies[i];
        const size_t span = 256 * sizeof(uint4);
        const dim3 grid((maximum_bytes + span - 1) / span, count);
        copy_batch_16<<<grid, 256, 0, context->stream>>>(
            static_cast<const char *>(source_base), static_cast<char *>(destination_base), batch);
        if (cudaGetLastError() != cudaSuccess) {
            cudaStreamSynchronize(context->stream);
            return 0;
        }
    } else {
        for (size_t i = 0; i < count; ++i) {
            const auto &copy = copies[i];
            if (cudaMemcpyAsync(static_cast<char *>(destination_base) + copy.destination_offset,
                    static_cast<char *>(source_base) + copy.source_offset, copy.bytes,
                    cudaMemcpyDeviceToDevice, context->stream) != cudaSuccess) {
                cudaStreamSynchronize(context->stream);
                return 0;
            }
        }
    }
    context->pending = true;
    return 1;
}

extern "C" int align_native_cuda_copy_wait(void *opaque) {
    auto *context = static_cast<CopyContext *>(opaque);
    if (context == nullptr || context->stream == nullptr
        || cudaSetDevice(context->device) != cudaSuccess) return 0;
#if defined(ALIGN_NATIVE_CUDA_FORCE_COMPLETION_FAILURE)
    const bool had_pending = context->pending;
#endif
    const cudaError_t status = cudaStreamSynchronize(context->stream);
    context->pending = false;
#if defined(ALIGN_NATIVE_CUDA_FORCE_COMPLETION_FAILURE)
    if (had_pending) {
        fprintf(stderr, "native_state_copy forced completion failure\n");
        return 0;
    }
#endif
    return status == cudaSuccess;
}

extern "C" void align_native_cuda_copy_close(void *opaque) {
    auto *context = static_cast<CopyContext *>(opaque);
    if (context == nullptr) return;
    if (context->stream != nullptr) {
        cudaSetDevice(context->device);
        cudaStreamSynchronize(context->stream);
        cudaStreamDestroy(context->stream);
    }
    delete context;
}
