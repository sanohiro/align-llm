// Diagnostic only: contiguous-read ceiling for the captured Q6_K weight bytes.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <vector>

static const char *shader = R"METAL(
#include <metal_stdlib>
using namespace metal;
kernel void checksum_read(
    device const uint4 *weights [[buffer(0)]],
    device uint *checksums [[buffer(1)]],
    constant uint &total_vectors [[buffer(2)]],
    uint group [[threadgroup_position_in_grid]],
    ushort thread_index [[thread_index_in_threadgroup]],
    ushort lane [[thread_index_in_simdgroup]],
    ushort simd [[simdgroup_index_in_threadgroup]]) {
    uint value = 0;
    const uint base = group * 1024 + thread_index;
    for (uint j = 0; j < 4; ++j) {
        uint index = base + j * 256;
        if (index < total_vectors) {
            uint4 item = weights[index];
            value += item.x + item.y + item.z + item.w;
        }
    }
    uint total = simd_sum(value);
    if (lane == 0) checksums[group * 8 + simd] = total;
}
)METAL";

static void need(bool ok, const char *message) {
    if (!ok) { std::fprintf(stderr, "Q6_STREAM error=%s\n", message); std::exit(1); }
}
struct Timing { double gpu_ms, wall_ms; };
int main(int argc, char **argv) {
    need(argc == 2, "usage: bench-q6-stream CAPTURED_WEIGHTS_BIN");
    constexpr size_t expected_bytes = 417177600;
    std::ifstream file(argv[1], std::ios::binary | std::ios::ate);
    need(bool(file) && file.tellg() == std::streamoff(expected_bytes), "unexpected captured weight extent");
    file.seekg(0);
    std::vector<uint32_t> words(expected_bytes / 4);
    file.read(reinterpret_cast<char *>(words.data()), expected_bytes);
    need(bool(file), "could not read complete weights");
    uint32_t expected = 0;
    for (uint32_t word : words) expected += word;
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice(); need(device != nil, "Metal unavailable");
        NSError *error = nil;
        id<MTLLibrary> library = [device newLibraryWithSource:
            [NSString stringWithUTF8String:shader] options:nil error:&error];
        if (!library) std::fprintf(stderr, "Metal compile: %s\n", error.localizedDescription.UTF8String);
        need(library != nil, "Metal compilation failed");
        id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:
            [library newFunctionWithName:@"checksum_read"] error:&error];
        need(pipeline != nil && pipeline.threadExecutionWidth == 32 &&
             pipeline.maxTotalThreadsPerThreadgroup >= 256, "pipeline geometry unavailable");
        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLBuffer> weights = [device newBufferWithBytes:words.data() length:expected_bytes
            options:MTLResourceStorageModeShared];
        const uint32_t vectors = expected_bytes / 16;
        const uint32_t groups = (vectors + 1023) / 1024;
        id<MTLBuffer> checksums = [device newBufferWithLength:size_t(groups) * 8 * 4
            options:MTLResourceStorageModeShared];
        need(queue && weights && checksums, "Metal allocation failed");
        std::vector<uint32_t>().swap(words);
        auto run = [&]() -> Timing {
            auto start = std::chrono::steady_clock::now();
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            need(command && encoder, "command allocation failed");
            [encoder setComputePipelineState:pipeline];
            [encoder setBuffer:weights offset:0 atIndex:0];
            [encoder setBuffer:checksums offset:0 atIndex:1];
            [encoder setBytes:&vectors length:sizeof(vectors) atIndex:2];
            [encoder dispatchThreadgroups:MTLSizeMake(groups, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
            [encoder endEncoding]; [command commit]; [command waitUntilCompleted];
            need(command.status == MTLCommandBufferStatusCompleted, "GPU command failed");
            need(command.GPUStartTime > 0 && command.GPUEndTime > command.GPUStartTime,
                 "GPU timing unavailable");
            double wall_ms = std::chrono::duration<double, std::milli>(
                std::chrono::steady_clock::now() - start).count();
            return {1000 * (command.GPUEndTime - command.GPUStartTime), wall_ms};
        };
        run();
        uint32_t actual = 0;
        const uint32_t *parts = static_cast<const uint32_t *>(checksums.contents);
        for (uint32_t i = 0; i < groups * 8; ++i) actual += parts[i];
        need(actual == expected, "complete CPU/GPU checksum differs");
        std::printf("{\"event\":\"check\",\"bytes\":%zu,\"vectors\":%u,\"groups\":%u,\"checksum\":%u}\n",
                    expected_bytes, vectors, groups, actual);
        for (int i = 0; i < 12; ++i) run();
        for (int pair = 0; pair < 5; ++pair) {
            double gpu = 0, wall = 0;
            for (int i = 0; i < 20; ++i) {
                Timing t = run(); gpu += t.gpu_ms; wall += t.wall_ms;
            }
            const double gpu_ms = gpu / 20;
            std::printf("{\"event\":\"pair\",\"pair\":%d,\"gpu_ms\":%.9f,\"wall_ms\":%.9f,\"read_gb_s\":%.6f}\n",
                        pair, gpu_ms, wall / 20, double(expected_bytes) / (1e6 * gpu_ms));
        }
    }
    return 0;
}
