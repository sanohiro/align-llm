// Optional Metal-only reduction boundary. Align owns generation and sampling policy.
// This helper only scans one synchronized, shared F32 output buffer and returns one index.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "ggml.h"
#include "ggml-backend-impl.h"
#include "ggml-metal-device.h"
#include <dlfcn.h>
#include <cstdint>
#include <climits>

static const char *source = R"METAL(
#include <metal_stdlib>
using namespace metal;
struct Part { float value; uint index; uint invalid; };
kernel void first(device const float *src [[buffer(0)]],
                  device Part *parts [[buffer(1)]],
                  constant uint &length [[buffer(2)]],
                  uint group [[threadgroup_position_in_grid]],
                  uint tid [[thread_index_in_threadgroup]]) {
    threadgroup float values[256];
    threadgroup uint indices[256];
    threadgroup uint invalids[256];
    float best = -INFINITY;
    uint index = 0xffffffffu;
    uint invalid = 0;
    for (uint j = group * 1024 + tid; j < min(length, (group + 1) * 1024); j += 256) {
        float v = src[j];
        if (!isfinite(v)) { invalid = 1; }
        else if (v > best || (v == best && j < index)) { best = v; index = j; }
    }
    values[tid] = best;
    indices[tid] = index;
    invalids[tid] = invalid;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = 128; stride > 0; stride >>= 1) {
        if (tid < stride) {
            invalids[tid] |= invalids[tid + stride];
            float other = values[tid + stride];
            uint other_index = indices[tid + stride];
            if (other > values[tid] || (other == values[tid] && other_index < indices[tid])) {
                values[tid] = other;
                indices[tid] = other_index;
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (tid == 0) parts[group] = {values[0], indices[0], invalids[0]};
}
kernel void second(device const Part *parts [[buffer(0)]],
                   device uint *result [[buffer(1)]],
                   constant uint &count [[buffer(2)]],
                   uint tid [[thread_index_in_threadgroup]]) {
    threadgroup float values[256];
    threadgroup uint indices[256];
    threadgroup uint invalids[256];
    float best = -INFINITY;
    uint index = 0xffffffffu;
    uint invalid = 0;
    for (uint j = tid; j < count; j += 256) {
        Part p = parts[j];
        invalid |= p.invalid;
        if (p.value > best || (p.value == best && p.index < index)) {
            best = p.value;
            index = p.index;
        }
    }
    values[tid] = best;
    indices[tid] = index;
    invalids[tid] = invalid;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = 128; stride > 0; stride >>= 1) {
        if (tid < stride) {
            invalids[tid] |= invalids[tid + stride];
            float other = values[tid + stride];
            uint other_index = indices[tid + stride];
            if (other > values[tid] || (other == values[tid] && other_index < indices[tid])) {
                values[tid] = other;
                indices[tid] = other_index;
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (tid == 0) result[0] = invalids[0] ? 0xffffffffu : indices[0];
}
)METAL";

@interface AlignMetalHierContext : NSObject
{
@public
    void *plugin;
    ggml_metal_buffer_id (*get_buffer_id)(ggml_metal_buffer_t, const ggml_tensor *);
    bool (*buffer_is_shared)(ggml_metal_buffer_t);
}
@property(strong) id<MTLDevice> device;
@property(strong) id<MTLCommandQueue> queue;
@property(strong) id<MTLComputePipelineState> first;
@property(strong) id<MTLComputePipelineState> second;
@property(strong) id<MTLBuffer> parts;
@property(strong) id<MTLBuffer> token;
@property(assign) uint32_t groups_capacity;
@end
@implementation AlignMetalHierContext
@end

extern "C" void *align_metal_hier_create(const char *plugin_path) {
    if (!plugin_path || plugin_path[0] != '/') return nullptr;
    @autoreleasepool {
        AlignMetalHierContext *ctx = [AlignMetalHierContext new];
        ctx->plugin = dlopen(plugin_path, RTLD_NOW | RTLD_LOCAL);
        if (!ctx->plugin) return nullptr;
        ctx->get_buffer_id = (ggml_metal_buffer_id (*)(ggml_metal_buffer_t, const ggml_tensor *))
            dlsym(ctx->plugin, "ggml_metal_buffer_get_id");
        ctx->buffer_is_shared = (bool (*)(ggml_metal_buffer_t))
            dlsym(ctx->plugin, "ggml_metal_buffer_is_shared");
        if (!ctx->get_buffer_id || !ctx->buffer_is_shared) {
            dlclose(ctx->plugin);
            return nullptr;
        }
        ctx.device = MTLCreateSystemDefaultDevice();
        if (!ctx.device) { dlclose(ctx->plugin); return nullptr; }
        ctx.queue = [ctx.device newCommandQueue];
        NSError *error = nil;
        id<MTLLibrary> library = [ctx.device newLibraryWithSource:
            [NSString stringWithUTF8String:source] options:nil error:&error];
        if (!library) { dlclose(ctx->plugin); return nullptr; }
        ctx.first = [ctx.device newComputePipelineStateWithFunction:
            [library newFunctionWithName:@"first"] error:&error];
        ctx.second = [ctx.device newComputePipelineStateWithFunction:
            [library newFunctionWithName:@"second"] error:&error];
        if (!ctx.queue || !ctx.first || !ctx.second) { dlclose(ctx->plugin); return nullptr; }
        ctx.token = [ctx.device newBufferWithLength:sizeof(uint32_t)
            options:MTLResourceStorageModeShared];
        if (!ctx.token) { dlclose(ctx->plugin); return nullptr; }
        return (void *)CFBridgingRetain(ctx);
    }
}

extern "C" int32_t align_metal_hier_run(void *opaque, void *backend_buffer_raw,
                                         void *tensor_raw, int64_t expected_bytes,
                                         int32_t *out_token) {
    if (!opaque || !backend_buffer_raw || !tensor_raw || !out_token
        || expected_bytes < 4 || expected_bytes % 4 || expected_bytes > 4194304) return -1;
    @autoreleasepool {
        AlignMetalHierContext *ctx = (__bridge AlignMetalHierContext *)opaque;
        ggml_backend_buffer_t backend_buffer = (ggml_backend_buffer_t)backend_buffer_raw;
        ggml_metal_buffer_t buffer = (ggml_metal_buffer_t)backend_buffer->context;
        ggml_tensor *tensor = (ggml_tensor *)tensor_raw;
        if (!ctx->buffer_is_shared(buffer)) return -1;
        ggml_metal_buffer_id bid = ctx->get_buffer_id(buffer, tensor);
        id<MTLBuffer> input = (__bridge id<MTLBuffer>)bid.metal;
        if (!input || input.device != ctx.device || bid.offs > input.length
            || (size_t)expected_bytes > input.length - bid.offs
            || (char *)input.contents + bid.offs != tensor->data) return -1;
        uint32_t length = (uint32_t)(expected_bytes / 4);
        uint32_t groups = (length + 1023) / 1024;
        if (!ctx.parts || groups > ctx.groups_capacity) {
            ctx.parts = [ctx.device newBufferWithLength:groups * 12
                options:MTLResourceStorageModeShared];
            if (!ctx.parts) return -1;
            ctx.groups_capacity = groups;
        }
        id<MTLCommandBuffer> command = [ctx.queue commandBuffer];
        if (!command) return -1;
        id<MTLComputeCommandEncoder> first = [command computeCommandEncoder];
        if (!first) return -1;
        [first setComputePipelineState:ctx.first];
        [first setBuffer:input offset:bid.offs atIndex:0];
        [first setBuffer:ctx.parts offset:0 atIndex:1];
        [first setBytes:&length length:sizeof(length) atIndex:2];
        [first dispatchThreadgroups:MTLSizeMake(groups, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        [first endEncoding];
        id<MTLComputeCommandEncoder> second = [command computeCommandEncoder];
        if (!second) return -1;
        [second setComputePipelineState:ctx.second];
        [second setBuffer:ctx.parts offset:0 atIndex:0];
        [second setBuffer:ctx.token offset:0 atIndex:1];
        [second setBytes:&groups length:sizeof(groups) atIndex:2];
        [second dispatchThreadgroups:MTLSizeMake(1, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        [second endEncoding];
        [command commit];
        [command waitUntilCompleted];
        if (command.status != MTLCommandBufferStatusCompleted) return -1;
        uint32_t value = *(uint32_t *)ctx.token.contents;
        if (value == UINT32_MAX) return -2;
        if (value >= length || value > INT32_MAX) return -1;
        *out_token = (int32_t)value;
        return 0;
    }
}

extern "C" void align_metal_hier_destroy(void *opaque) {
    if (opaque) {
        @autoreleasepool {
            AlignMetalHierContext *ctx = (__bridge AlignMetalHierContext *)opaque;
            if (ctx->plugin) dlclose(ctx->plugin);
            (void)CFBridgingRelease(opaque);
        }
    }
}
