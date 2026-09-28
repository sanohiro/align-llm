// Device-only batch copy. Align selects graph producers and resident destinations.
// ggml owns the borrowed shared allocations; this module owns the Metal command.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include "native_metal_state_copy.h"
#include "native_metal_target_greedy_kernel.h"

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
    id<MTLBuffer> greedy_view;
    id<MTLBuffer> greedy_parts;
    id<MTLBuffer> greedy_result;
    id<MTLComputePipelineState> greedy_partial_pipeline;
    id<MTLComputePipelineState> greedy_final_pipeline;
    id<MTLBuffer> target_greedy_view;
    id<MTLBuffer> target_greedy_parts;
    id<MTLBuffer> target_greedy_result;
    id<MTLComputePipelineState> target_greedy_partial_pipeline;
    id<MTLComputePipelineState> target_greedy_final_pipeline;
    id<MTLCommandBuffer> pending;
    void *source_base;
    void *destination_base;
    size_t source_length;
    size_t destination_length;
    void *greedy_base;
    size_t greedy_length;
    void *target_greedy_base;
    size_t target_greedy_length;
    size_t pending_count;
    bool pending_greedy;
    bool greedy_ready;
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
        auto *context = new align_native_metal_copy_context{};
        context->device = device;
        context->queue = queue;
        context->trace = trace != nullptr && trace[0] == '1' && trace[1] == '\0';
        return context;
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

extern "C" int align_native_metal_copy_enable_greedy(void *opaque) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    if (context == nullptr || context->pending != nil) return 0;
    if (context->greedy_partial_pipeline != nil && context->greedy_final_pipeline != nil
        && context->greedy_parts != nil && context->greedy_result != nil) return 1;
    static const char *source = R"metal(
#include <metal_stdlib>
using namespace metal;
struct Part { float value; uint index; uint invalid; };
kernel void greedy_partial(device const float *input [[buffer(0)]],
                           device Part *parts [[buffer(1)]],
                           constant uint &length [[buffer(2)]],
                           uint group [[threadgroup_position_in_grid]],
                           uint lane [[thread_index_in_threadgroup]]) {
    threadgroup float values[256];
    threadgroup uint indices[256];
    threadgroup uint invalids[256];
    float best = -INFINITY;
    uint index = 0xffffffffu;
    uint invalid = 0;
    for (uint j = group * 1024 + lane; j < min(length, (group + 1) * 1024); j += 256) {
        float value = input[j];
        if (!isfinite(value)) invalid = 1;
        else if (value > best || (value == best && j < index)) {
            best = value;
            index = j;
        }
    }
    values[lane] = best;
    indices[lane] = index;
    invalids[lane] = invalid;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = 128; stride > 0; stride >>= 1) {
        if (lane < stride) {
            invalids[lane] |= invalids[lane + stride];
            float value = values[lane + stride];
            uint other = indices[lane + stride];
            if (value > values[lane] || (value == values[lane] && other < indices[lane])) {
                values[lane] = value;
                indices[lane] = other;
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (lane == 0) parts[group] = {values[0], indices[0], invalids[0]};
}
kernel void greedy_final(device const Part *parts [[buffer(0)]],
                         device uint *result [[buffer(1)]],
                         constant uint &count [[buffer(2)]],
                         uint lane [[thread_index_in_threadgroup]]) {
    threadgroup float values[256];
    threadgroup uint indices[256];
    threadgroup uint invalids[256];
    float best = -INFINITY;
    uint index = 0xffffffffu;
    uint invalid = 0;
    for (uint j = lane; j < count; j += 256) {
        Part part = parts[j];
        invalid |= part.invalid;
        if (part.value > best || (part.value == best && part.index < index)) {
            best = part.value;
            index = part.index;
        }
    }
    values[lane] = best;
    indices[lane] = index;
    invalids[lane] = invalid;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = 128; stride > 0; stride >>= 1) {
        if (lane < stride) {
            invalids[lane] |= invalids[lane + stride];
            float value = values[lane + stride];
            uint other = indices[lane + stride];
            if (value > values[lane] || (value == values[lane] && other < indices[lane])) {
                values[lane] = value;
                indices[lane] = other;
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (lane == 0) result[0] = invalids[0] ? 0xffffffffu : indices[0];
}
)metal";
    @autoreleasepool {
        NSError *error = nil;
        id<MTLLibrary> library = [context->device
            newLibraryWithSource:[NSString stringWithUTF8String:source] options:nil error:&error];
        if (library == nil) return 0;
        id<MTLFunction> partial = [library newFunctionWithName:@"greedy_partial"];
        id<MTLFunction> final = [library newFunctionWithName:@"greedy_final"];
        if (partial == nil || final == nil) return 0;
        id<MTLComputePipelineState> first =
            [context->device newComputePipelineStateWithFunction:partial error:&error];
        id<MTLComputePipelineState> second =
            [context->device newComputePipelineStateWithFunction:final error:&error];
        if (first == nil || second == nil || first.maxTotalThreadsPerThreadgroup < 256
            || second.maxTotalThreadsPerThreadgroup < 256) return 0;
        id<MTLBuffer> parts = [context->device newBufferWithLength:1024 * 12
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> result = [context->device newBufferWithLength:sizeof(uint32_t)
            options:MTLResourceStorageModeShared];
        if (parts == nil || result == nil || result.contents == nullptr) return 0;
        context->greedy_partial_pipeline = first;
        context->greedy_final_pipeline = second;
        context->greedy_parts = parts;
        context->greedy_result = result;
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
    context->greedy_ready = succeeded && context->pending_greedy;
    context->pending_greedy = false;
#if defined(ALIGN_NATIVE_METAL_FORCE_COMPLETION_FAILURE)
    // Test build: report a failed completion after draining the real command.
    if (succeeded) {
        context->greedy_ready = false;
        fprintf(stderr, "native_state_copy forced completion failure\n");
        return 0;
    }
#endif
    return succeeded ? 1 : 0;
}

extern "C" int64_t align_native_metal_copy_greedy_result(void *opaque) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    if (context == nullptr || context->pending != nil || !context->greedy_ready
        || context->greedy_result == nil || context->greedy_result.contents == nullptr) return -1;
    context->greedy_ready = false;
    uint32_t token = *static_cast<const uint32_t *>(context->greedy_result.contents);
    return token == UINT32_MAX ? -2 : int64_t(token);
}

extern "C" int align_native_metal_target_greedy_run(void *opaque, void *base, size_t size,
        uint64_t offset, uint32_t rows, uint32_t width, uint32_t *result) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    size_t page = size_t(getpagesize());
    if (context == nullptr || context->pending != nil || base == nullptr || result == nullptr
        || page == 0 || uintptr_t(base) % page != 0 || size == 0
        || rows < 2 || rows > 16 || width == 0 || width > 1048576
        || offset % sizeof(float) != 0) return 0;
    uint32_t groups = (width + 1023) / 1024;
    size_t parts_bytes = size_t(rows) * groups * 12;
    size_t result_bytes = size_t(rows) * sizeof(uint32_t);
    if (parts_bytes + result_bytes > 16384 || size > SIZE_MAX - (page - 1)) return 0;
    size_t padded = (size + page - 1) / page * page;
    uint64_t input_bytes = uint64_t(rows) * width * sizeof(float);
    if (padded > context->device.maxBufferLength || offset > padded
        || input_bytes > padded - offset) return 0;
    @autoreleasepool {
        if (context->target_greedy_partial_pipeline == nil
            || context->target_greedy_final_pipeline == nil) {
            NSError *error = nil;
            id<MTLLibrary> library = [context->device newLibraryWithSource:
                [NSString stringWithUTF8String:kTargetGreedyShader] options:nil error:&error];
            if (library == nil) return 0;
            id<MTLFunction> partial = [library newFunctionWithName:@"partial"];
            id<MTLFunction> final = [library newFunctionWithName:@"finish"];
            if (partial == nil || final == nil) return 0;
            id<MTLComputePipelineState> first =
                [context->device newComputePipelineStateWithFunction:partial error:&error];
            id<MTLComputePipelineState> second =
                [context->device newComputePipelineStateWithFunction:final error:&error];
            if (first == nil || second == nil || first.maxTotalThreadsPerThreadgroup < 256
                || second.maxTotalThreadsPerThreadgroup < 256) return 0;
            context->target_greedy_partial_pipeline = first;
            context->target_greedy_final_pipeline = second;
        }
        if (context->target_greedy_parts == nil
            || context->target_greedy_parts.length < parts_bytes) {
            context->target_greedy_parts = [context->device newBufferWithLength:parts_bytes
                options:MTLResourceStorageModeShared];
        }
        if (context->target_greedy_result == nil
            || context->target_greedy_result.length < result_bytes) {
            context->target_greedy_result = [context->device newBufferWithLength:result_bytes
                options:MTLResourceStorageModeShared];
        }
        if (context->target_greedy_view == nil || context->target_greedy_base != base
            || context->target_greedy_length != padded) {
            context->target_greedy_view = [context->device newBufferWithBytesNoCopy:base
                length:padded options:MTLResourceStorageModeShared
                deallocator:^(void *, NSUInteger) {}];
            context->target_greedy_base = base;
            context->target_greedy_length = padded;
        }
        if (context->target_greedy_parts == nil || context->target_greedy_result == nil
            || context->target_greedy_result.contents == nullptr
            || context->target_greedy_view == nil
            || context->target_greedy_view.contents != base) return 0;
#if defined(ALIGN_NATIVE_METAL_FORCE_SUBMIT_FAILURE)
        fprintf(stderr, "native_target_greedy forced submit failure\n");
        return 0;
#endif
        id<MTLCommandBuffer> command = [context->queue commandBuffer];
        if (command == nil) return 0;
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        if (encoder == nil) return 0;
        [encoder setComputePipelineState:context->target_greedy_partial_pipeline];
        [encoder setBuffer:context->target_greedy_view offset:size_t(offset) atIndex:0];
        [encoder setBuffer:context->target_greedy_parts offset:0 atIndex:1];
        [encoder setBytes:&width length:sizeof(width) atIndex:2];
        [encoder setBytes:&groups length:sizeof(groups) atIndex:3];
        [encoder dispatchThreadgroups:MTLSizeMake(groups, rows, 1)
            threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
        [encoder setComputePipelineState:context->target_greedy_final_pipeline];
        [encoder setBuffer:context->target_greedy_parts offset:0 atIndex:0];
        [encoder setBuffer:context->target_greedy_result offset:0 atIndex:1];
        [encoder setBytes:&groups length:sizeof(groups) atIndex:2];
        [encoder dispatchThreadgroups:MTLSizeMake(rows, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        [encoder endEncoding];
        [command commit];
        [command waitUntilCompleted];
        if (command.status != MTLCommandBufferStatusCompleted) return 0;
#if defined(ALIGN_NATIVE_METAL_FORCE_COMPLETION_FAILURE)
        fprintf(stderr, "native_target_greedy forced completion failure\n");
        return 0;
#endif
        const uint32_t *values = static_cast<const uint32_t *>(
            context->target_greedy_result.contents);
        for (uint32_t row = 0; row < rows; ++row) {
            if (values[row] == UINT32_MAX || values[row] >= width) return 0;
        }
        memcpy(result, values, result_bytes);
        return 1;
    }
}

extern "C" int align_native_metal_copy_reset_views(void *opaque) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    if (context == nullptr) return 0;
    int completed = align_native_metal_copy_wait(context);
    context->source_view = nil;
    context->destination_view = nil;
    context->greedy_view = nil;
    context->target_greedy_view = nil;
    context->source_base = nullptr;
    context->destination_base = nullptr;
    context->source_length = 0;
    context->destination_length = 0;
    context->greedy_base = nullptr;
    context->greedy_length = 0;
    context->target_greedy_base = nullptr;
    context->target_greedy_length = 0;
    context->greedy_ready = false;
    return completed;
}

extern "C" int align_native_metal_copy_submit(void *opaque,
        void *source_base, size_t source_size,
        void *destination_base, size_t destination_size,
        const struct align_native_metal_copy *copies, size_t count,
        const struct align_native_metal_strided_copy *strided, size_t strided_count,
        const struct align_native_metal_greedy_input *greedy) {
    auto *context = static_cast<align_native_metal_copy_context *>(opaque);
    size_t page = size_t(getpagesize());
    if (context == nullptr || context->pending != nil || page == 0
        || source_base == nullptr || destination_base == nullptr
        || count > 64 || strided_count > 64 || count + strided_count == 0
        || (count > 0 && copies == nullptr) || (strided_count > 0 && strided == nullptr)
        || (strided_count > 0
            && (context->strided_pipeline == nil || context->strided_descriptors == nil))
        || (greedy != nullptr && (context->greedy_partial_pipeline == nil
            || context->greedy_final_pipeline == nil || context->greedy_parts == nil
            || context->greedy_result == nil || greedy->base == nullptr
            || greedy->count == 0 || greedy->count > 1048576
            || uintptr_t(greedy->base) % page != 0))
        || uintptr_t(source_base) % page != 0 || uintptr_t(destination_base) % page != 0) return 0;
    size_t source_length = source_size - source_size % page;
    size_t destination_length = destination_size - destination_size % page;
    if (source_length == 0 || destination_length == 0
        || source_length > context->device.maxBufferLength
        || destination_length > context->device.maxBufferLength) return 0;
    size_t greedy_length = 0;
    if (greedy != nullptr) {
        // The selected pinned ggml Metal shared allocator allocates and wraps
        // its logical buffer size rounded up to a page. Decode logits end at
        // the logical workspace tail, so a floor-length view would exclude
        // part of the row even though ggml's own Metal view covers it.
        size_t padding = (page - greedy->size % page) % page;
        if (greedy->size > SIZE_MAX - padding) return 0;
        greedy_length = greedy->size + padding;
        uint64_t bytes = uint64_t(greedy->count) * sizeof(float);
        if (greedy_length == 0 || greedy_length > context->device.maxBufferLength
            || greedy->offset % sizeof(float) != 0 || greedy->offset > greedy_length
            || bytes > greedy_length - greedy->offset) return 0;
    }
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
        if (greedy != nullptr && (context->greedy_view == nil
            || context->greedy_base != greedy->base
            || context->greedy_length != greedy_length)) {
            context->greedy_view = [context->device
                newBufferWithBytesNoCopy:greedy->base length:greedy_length
                options:MTLResourceStorageModeShared deallocator:^(void *, NSUInteger) {}];
            context->greedy_base = greedy->base;
            context->greedy_length = greedy_length;
        }
        if (context->source_view == nil || context->destination_view == nil
            || (greedy != nullptr && context->greedy_view == nil)
            || (greedy != nullptr && context->greedy_view.contents != greedy->base)
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
        if (strided_count > 0 || greedy != nullptr) {
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            if (encoder == nil) return 0;
            if (strided_count > 0) {
                memcpy(context->strided_descriptors.contents, strided,
                       strided_count * sizeof(align_native_metal_strided_copy));
                [encoder setComputePipelineState:context->strided_pipeline];
                [encoder setBuffer:context->source_view offset:0 atIndex:0];
                [encoder setBuffer:context->destination_view offset:0 atIndex:1];
                [encoder setBuffer:context->strided_descriptors offset:0 atIndex:2];
                NSUInteger threads = context->strided_pipeline.maxTotalThreadsPerThreadgroup;
                if (threads > 256) threads = 256;
                [encoder dispatchThreads:MTLSizeMake(max_strided_elements, strided_count, 1)
                    threadsPerThreadgroup:MTLSizeMake(threads, 1, 1)];
            }
            if (greedy != nullptr) {
                uint32_t groups = (greedy->count + 1023) / 1024;
                *static_cast<uint32_t *>(context->greedy_result.contents) = UINT32_MAX;
                [encoder setComputePipelineState:context->greedy_partial_pipeline];
                [encoder setBuffer:context->greedy_view offset:greedy->offset atIndex:0];
                [encoder setBuffer:context->greedy_parts offset:0 atIndex:1];
                [encoder setBytes:&greedy->count length:sizeof(greedy->count) atIndex:2];
                [encoder dispatchThreadgroups:MTLSizeMake(groups, 1, 1)
                    threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
                [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
                [encoder setComputePipelineState:context->greedy_final_pipeline];
                [encoder setBuffer:context->greedy_parts offset:0 atIndex:0];
                [encoder setBuffer:context->greedy_result offset:0 atIndex:1];
                [encoder setBytes:&groups length:sizeof(groups) atIndex:2];
                [encoder dispatchThreadgroups:MTLSizeMake(1, 1, 1)
                    threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
            }
            [encoder endEncoding];
        }
        [command commit];
        context->pending = command;
        context->pending_count = count + strided_count + (greedy == nullptr ? 0 : 1);
        context->pending_greedy = greedy != nullptr;
        context->greedy_ready = false;
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
