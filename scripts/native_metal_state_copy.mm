// Device-only batch copy. Align selects graph producers and resident destinations.
// ggml owns the borrowed shared allocations; this module owns the Metal command.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include "native_metal_state_copy.h"

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

struct align_native_metal_copy_context {
    id<MTLDevice> device;
    id<MTLCommandQueue> queue;
    id<MTLBuffer> source_view;
    id<MTLBuffer> destination_view;
    id<MTLBuffer> strided_descriptors;
    id<MTLComputePipelineState> strided_pipeline;
    id<MTLCommandBuffer> pending;
    void *source_base;
    void *destination_base;
    size_t source_length;
    size_t destination_length;
    size_t pending_count;
    uint64_t preparation_ns;
    uint64_t submitted_ns;
    bool trace;
};

static uint64_t clock_ns(void) {
    struct timespec time;
    clock_gettime(CLOCK_MONOTONIC, &time);
    return uint64_t(time.tv_sec) * 1000000000 + uint64_t(time.tv_nsec);
}

extern "C" void *align_native_metal_copy_open(const char *selected_device_description) {
    @autoreleasepool {
        // The pinned ggml Metal backend constructs MTL0 from the system default
        // device. Admit this borrowed-allocation path only when that identity is
        // unambiguous; other devices retain the ordinary ggml copy graph.
        NSArray<id<MTLDevice>> *devices = MTLCopyAllDevices();
        if (selected_device_description == nullptr || devices.count != 1) return nullptr;
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (device == nil || device.registryID != devices.firstObject.registryID
            || !device.hasUnifiedMemory
            || strcmp(selected_device_description, device.name.UTF8String) != 0) return nullptr;
        id<MTLCommandQueue> queue = [device newCommandQueue];
        if (queue == nil) return nullptr;
        const char *trace = getenv("ALIGN_LLM_NATIVE_COPY_TRACE");
        return new align_native_metal_copy_context{
            device, queue, nil, nil, nil, nil, nil, nullptr, nullptr, 0, 0, 0, 0, 0,
            trace != nullptr && trace[0] == '1' && trace[1] == '\0'};
    }
}

extern "C" int align_native_metal_copy_enable_strided(void *opaque) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    if (context == nullptr || context->pending != nil) return 0;
    if (context->strided_pipeline != nil && context->strided_descriptors != nil) return 1;
    static const char *source = R"metal(
#include <metal_stdlib>
using namespace metal;
struct Copy {
    ulong source_offset;
    ulong destination_offset;
    uint row_elements;
    uint rows;
    uint source_row_stride;
    uint destination_row_stride;
};
kernel void copy_strided(device const uchar *source [[buffer(0)]],
                         device uchar *destination [[buffer(1)]],
                         device const Copy *copies [[buffer(2)]],
                         uint2 position [[thread_position_in_grid]]) {
    Copy item = copies[position.y];
    if (item.row_elements == 3) {
        if (position.x >= item.rows) return;
        device const uint *from = (device const uint *)(source + item.source_offset
            + ulong(position.x) * item.source_row_stride);
        device uint *to = (device uint *)(destination + item.destination_offset
            + ulong(position.x) * item.destination_row_stride);
        to[0] = from[0];
        to[1] = from[1];
        to[2] = from[2];
        return;
    }
    uint elements = item.row_elements * item.rows;
    if (position.x >= elements) return;
    ulong row = position.x / item.row_elements;
    ulong column = position.x % item.row_elements;
    device const uint *from = (device const uint *)(source + item.source_offset
        + row * item.source_row_stride + column * sizeof(float));
    device uint *to = (device uint *)(destination + item.destination_offset
        + row * item.destination_row_stride + column * sizeof(float));
    *to = *from;
}
)metal";
    @autoreleasepool {
        NSError *error = nil;
        NSString *text = [NSString stringWithUTF8String:source];
        id<MTLLibrary> library = [context->device newLibraryWithSource:text options:nil error:&error];
        if (library == nil) return 0;
        id<MTLFunction> function = [library newFunctionWithName:@"copy_strided"];
        if (function == nil) return 0;
        id<MTLComputePipelineState> pipeline =
            [context->device newComputePipelineStateWithFunction:function error:&error];
        if (pipeline == nil || pipeline.maxTotalThreadsPerThreadgroup < 1) return 0;
        id<MTLBuffer> descriptors = [context->device
            newBufferWithLength:sizeof(align_native_metal_strided_copy) * 64
            options:MTLResourceStorageModeShared];
        if (descriptors == nil || descriptors.contents == nullptr) return 0;
        context->strided_pipeline = pipeline;
        context->strided_descriptors = descriptors;
        return 1;
    }
}

extern "C" int align_native_metal_copy_wait(void *opaque) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    if (context == nullptr) return 0;
    if (context->pending == nil) return 1;
    uint64_t wait_start = context->trace ? clock_ns() : 0;
    [context->pending waitUntilCompleted];
    bool succeeded = context->pending.status == MTLCommandBufferStatusCompleted;
    if (context->trace) {
        uint64_t finished = clock_ns();
        fprintf(stderr,
            "native_state_copy records=%zu preparation_ns=%llu wait_ns=%llu total_ns=%llu gpu_ns=%llu\n",
            context->pending_count,
            (unsigned long long) context->preparation_ns,
            (unsigned long long) (finished - wait_start),
            (unsigned long long) (finished - context->submitted_ns),
            (unsigned long long) ((context->pending.GPUEndTime - context->pending.GPUStartTime) * 1e9));
    }
    context->pending = nil;
    context->pending_count = 0;
#if defined(ALIGN_NATIVE_METAL_FORCE_COMPLETION_FAILURE)
    // Test build: report a failed completion after draining the real command.
    if (succeeded) {
        fprintf(stderr, "native_state_copy forced completion failure\n");
        return 0;
    }
#endif
    return succeeded ? 1 : 0;
}

extern "C" int align_native_metal_copy_reset_views(void *opaque) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    if (context == nullptr) return 0;
    int completed = align_native_metal_copy_wait(context);
    context->source_view = nil;
    context->destination_view = nil;
    context->source_base = nullptr;
    context->destination_base = nullptr;
    context->source_length = 0;
    context->destination_length = 0;
    return completed;
}

extern "C" int align_native_metal_copy_submit(void *opaque,
        void *source_base, size_t source_size,
        void *destination_base, size_t destination_size,
        const struct align_native_metal_copy *copies, size_t count,
        const struct align_native_metal_strided_copy *strided, size_t strided_count) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    size_t page = size_t(getpagesize());
    if (context == nullptr || context->pending != nil
        || source_base == nullptr || destination_base == nullptr
        || count > 64 || strided_count > 64 || count + strided_count == 0
        || (count > 0 && copies == nullptr) || (strided_count > 0 && strided == nullptr)
        || (strided_count > 0
            && (context->strided_pipeline == nil || context->strided_descriptors == nil))
        || page == 0
        || uintptr_t(source_base) % page != 0 || uintptr_t(destination_base) % page != 0) return 0;
    size_t source_length = source_size - source_size % page;
    size_t destination_length = destination_size - destination_size % page;
    if (source_length == 0 || destination_length == 0
        || source_length > context->device.maxBufferLength
        || destination_length > context->device.maxBufferLength) return 0;
    for (size_t i = 0; i < count; ++i) {
        const auto &item = copies[i];
        uint64_t bytes = uint64_t(item.elements) * sizeof(float);
        if (item.reserved != 0 || item.elements < 262144
            || item.source_offset % 4 != 0 || item.destination_offset % 4 != 0
            || item.source_offset > source_length || bytes > source_length - item.source_offset
            || item.destination_offset > destination_length
            || bytes > destination_length - item.destination_offset) return 0;
    }
    uint32_t max_strided_elements = 0;
    for (size_t i = 0; i < strided_count; ++i) {
        const auto &item = strided[i];
        uint64_t row_bytes = uint64_t(item.row_elements) * sizeof(float);
        uint64_t elements = uint64_t(item.row_elements) * item.rows;
        if (item.row_elements == 0 || item.rows == 0 || elements > INT32_MAX
            || item.source_offset % 4 != 0 || item.destination_offset % 4 != 0
            || item.source_row_stride < row_bytes || item.destination_row_stride != row_bytes
            || item.source_row_stride % 4 != 0 || item.destination_row_stride % 4 != 0
            || item.source_offset > source_length || item.destination_offset > destination_length
            || uint64_t(item.rows - 1) * item.source_row_stride + row_bytes
                > source_length - item.source_offset
            || uint64_t(item.rows - 1) * item.destination_row_stride + row_bytes
                > destination_length - item.destination_offset) return 0;
        uint32_t work = item.row_elements == 3 ? item.rows : uint32_t(elements);
        if (work > max_strided_elements) max_strided_elements = work;
    }
    @autoreleasepool {
        uint64_t preparation_start = context->trace ? clock_ns() : 0;
        // A workspace rebuild calls reset_views before freeing the old ggml
        // allocation. Otherwise the same wrapper is reused for every token.
        if (context->source_view == nil || context->source_base != source_base
            || context->source_length != source_length) {
            context->source_view = [context->device
                newBufferWithBytesNoCopy:source_base length:source_length
                options:MTLResourceStorageModeShared deallocator:^(void *, NSUInteger) {}];
            context->source_base = source_base;
            context->source_length = source_length;
        }
        if (context->destination_view == nil || context->destination_base != destination_base
            || context->destination_length != destination_length) {
            context->destination_view = [context->device
                newBufferWithBytesNoCopy:destination_base length:destination_length
                options:MTLResourceStorageModeShared deallocator:^(void *, NSUInteger) {}];
            context->destination_base = destination_base;
            context->destination_length = destination_length;
        }
        if (context->source_view == nil || context->destination_view == nil
            || context->source_view.contents != source_base
            || context->destination_view.contents != destination_base) return 0;
#if defined(ALIGN_NATIVE_METAL_FORCE_SUBMIT_FAILURE)
        // Test build: exercise the caller's submit-failure path with real views.
        fprintf(stderr, "native_state_copy forced submit failure\n");
        return 0;
#endif
        id<MTLCommandBuffer> command = [context->queue commandBuffer];
        if (command == nil) return 0;
        if (count > 0) {
            id<MTLBlitCommandEncoder> encoder = [command blitCommandEncoder];
            if (encoder == nil) return 0;
            for (size_t i = 0; i < count; ++i) {
                const auto &item = copies[i];
                [encoder copyFromBuffer:context->source_view sourceOffset:item.source_offset
                              toBuffer:context->destination_view destinationOffset:item.destination_offset
                                  size:size_t(item.elements) * sizeof(float)];
            }
            [encoder endEncoding];
        }
        if (strided_count > 0) {
            memcpy(context->strided_descriptors.contents, strided,
                   strided_count * sizeof(align_native_metal_strided_copy));
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            if (encoder == nil) return 0;
            [encoder setComputePipelineState:context->strided_pipeline];
            [encoder setBuffer:context->source_view offset:0 atIndex:0];
            [encoder setBuffer:context->destination_view offset:0 atIndex:1];
            [encoder setBuffer:context->strided_descriptors offset:0 atIndex:2];
            NSUInteger threads = context->strided_pipeline.maxTotalThreadsPerThreadgroup;
            if (threads > 256) threads = 256;
            [encoder dispatchThreads:MTLSizeMake(max_strided_elements, strided_count, 1)
                threadsPerThreadgroup:MTLSizeMake(threads, 1, 1)];
            [encoder endEncoding];
        }
        [command commit];
        context->pending = command;
        context->pending_count = count + strided_count;
        if (context->trace) {
            context->preparation_ns = clock_ns() - preparation_start;
            context->submitted_ns = clock_ns();
        }
        return 1;
    }
}

extern "C" void align_native_metal_copy_close(void *opaque) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    if (context == nullptr) return;
    align_native_metal_copy_reset_views(context);
    delete context;
}
