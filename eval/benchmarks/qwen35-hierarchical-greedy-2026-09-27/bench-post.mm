#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <limits>
#include <string>
#include <vector>

static const char *metal_source = R"METAL(
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

static uint32_t cpu_greedy(const float *values, size_t count) {
    float best = -INFINITY;
    uint32_t index = UINT32_MAX;
    for (size_t i = 0; i < count; i++) {
        float value = values[i];
        if (!std::isfinite(value)) return UINT32_MAX;
        if (value > best) { best = value; index = (uint32_t) i; }
    }
    return index;
}

struct Times { int64_t wall_ns; int64_t gpu_ns; uint32_t token; };

int main(int argc, char **argv) {
    if (argc < 2) { std::fprintf(stderr, "usage: bench REAL_LOGITS.bin [... ]\n"); return 2; }
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        id<MTLCommandQueue> queue = [device newCommandQueue];
        NSError *error = nil;
        NSString *source = [NSString stringWithUTF8String:metal_source];
        id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
        if (!library) { std::fprintf(stderr, "%s\n", error.localizedDescription.UTF8String); return 1; }
        id<MTLComputePipelineState> p1 = [device newComputePipelineStateWithFunction:[library newFunctionWithName:@"first"] error:&error];
        id<MTLComputePipelineState> p2 = [device newComputePipelineStateWithFunction:[library newFunctionWithName:@"second"] error:&error];
        if (!p1 || !p2) { std::fprintf(stderr, "%s\n", error.localizedDescription.UTF8String); return 1; }
        std::printf("kind,path,iteration,order,wall_ns,gpu_ns,token\n");
        for (int file = 1; file < argc; file++) {
            std::ifstream input(argv[file], std::ios::binary);
            std::vector<char> bytes((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
            if (bytes.empty() || bytes.size() % sizeof(float) != 0 || bytes.size() > UINT32_MAX) {
                std::fprintf(stderr, "bad input: %s\n", argv[file]); return 1;
            }
            uint32_t length = (uint32_t) (bytes.size() / sizeof(float));
            uint32_t groups = (length + 1023) / 1024;
            id<MTLBuffer> source_buffer = [device newBufferWithLength:bytes.size() options:MTLResourceStorageModeShared];
            id<MTLBuffer> result_buffer = [device newBufferWithLength:bytes.size() options:MTLResourceStorageModeShared];
            id<MTLBuffer> parts_buffer = [device newBufferWithLength:groups * 12 options:MTLResourceStorageModeShared];
            id<MTLBuffer> token_buffer = [device newBufferWithLength:4 options:MTLResourceStorageModeShared];
            if (!source_buffer || !result_buffer || !parts_buffer || !token_buffer) return 1;
            std::memcpy(source_buffer.contents, bytes.data(), bytes.size());
            uint32_t expected = cpu_greedy((const float *) bytes.data(), length);

            auto run = [&](bool hierarchical) -> Times {
                @autoreleasepool {
                    auto start = std::chrono::steady_clock::now();
                    id<MTLCommandBuffer> cb = [queue commandBuffer];
                    id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
                    [blit copyFromBuffer:source_buffer sourceOffset:0 toBuffer:result_buffer destinationOffset:0 size:bytes.size()];
                    [blit endEncoding];
                    if (hierarchical) {
                        [cb commit];
                        [cb waitUntilCompleted];
                        if (cb.status != MTLCommandBufferStatusCompleted) std::exit(1);
                        cb = [queue commandBuffer];
                        id<MTLComputeCommandEncoder> enc1 = [cb computeCommandEncoder];
                        [enc1 setComputePipelineState:p1];
                        [enc1 setBuffer:result_buffer offset:0 atIndex:0];
                        [enc1 setBuffer:parts_buffer offset:0 atIndex:1];
                        [enc1 setBytes:&length length:sizeof(length) atIndex:2];
                        [enc1 dispatchThreadgroups:MTLSizeMake(groups, 1, 1) threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
                        [enc1 endEncoding];
                        id<MTLComputeCommandEncoder> enc2 = [cb computeCommandEncoder];
                        [enc2 setComputePipelineState:p2];
                        [enc2 setBuffer:parts_buffer offset:0 atIndex:0];
                        [enc2 setBuffer:token_buffer offset:0 atIndex:1];
                        [enc2 setBytes:&groups length:sizeof(groups) atIndex:2];
                        [enc2 dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
                        [enc2 endEncoding];
                    }
                    [cb commit];
                    [cb waitUntilCompleted];
                    if (cb.status != MTLCommandBufferStatusCompleted) {
                        std::fprintf(stderr, "Metal command failed: %s\n", cb.error.localizedDescription.UTF8String);
                        std::exit(1);
                    }
                    uint32_t token = hierarchical ? *(uint32_t *) token_buffer.contents
                                                  : cpu_greedy((const float *) result_buffer.contents, length);
                    auto end = std::chrono::steady_clock::now();
                    auto wall = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
                    auto gpu = (int64_t) ((cb.GPUEndTime - cb.GPUStartTime) * 1e9);
                    return {wall, gpu, token};
                }
            };

            if (run(false).token != expected || run(true).token != expected) {
                std::fprintf(stderr, "actual vector mismatch: %s\n", argv[file]); return 1;
            }
            std::vector<char> modified = bytes;
            float *v = (float *) modified.data();
            float maxv = v[expected];
            v[1] = maxv + 1.0f;
            v[length - 2] = maxv + 1.0f;
            for (int case_id = 0; case_id < 3; case_id++) {
                if (case_id == 1) v[17] = std::numeric_limits<float>::quiet_NaN();
                if (case_id == 2) v[17] = std::numeric_limits<float>::infinity();
                std::memcpy(source_buffer.contents, modified.data(), modified.size());
                uint32_t want = case_id == 0 ? 1u : UINT32_MAX;
                if (run(false).token != want || run(true).token != want) {
                    std::fprintf(stderr, "tie/nonfinite mismatch: %s case %d\n", argv[file], case_id); return 1;
                }
            }
            std::memcpy(source_buffer.contents, bytes.data(), bytes.size());
            std::fprintf(stderr, "correctness PASS: %s, %u logits, token %u, tie/NaN/Inf\n", argv[file], length, expected);

            for (int i = 0; i < 100; i++) {
                if (run(false).token != expected || run(true).token != expected) return 1;
            }
            for (int i = 0; i < 100; i++) {
                bool reversed = (i % 2) != 0;
                Times a = run(reversed);
                Times b = run(!reversed);
                if (a.token != expected || b.token != expected) return 1;
                Times control = reversed ? b : a;
                Times candidate = reversed ? a : b;
                std::printf("control,%s,%d,%s,%lld,%lld,%u\n", argv[file], i, reversed ? "candidate-first" : "control-first",
                            (long long) control.wall_ns, (long long) control.gpu_ns, control.token);
                std::printf("candidate,%s,%d,%s,%lld,%lld,%u\n", argv[file], i, reversed ? "candidate-first" : "control-first",
                            (long long) candidate.wall_ns, (long long) candidate.gpu_ns, candidate.token);
            }
        }
    }
    return 0;
}
