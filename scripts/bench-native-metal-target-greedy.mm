// Developer-only bounded comparison for actual target logits. No model inference.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include "native_metal_target_greedy_kernel.h"

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr uint32_t kTile = 1024;
constexpr uint32_t kThreads = 256;
constexpr uint32_t kInvalid = UINT32_MAX;



using Clock = std::chrono::steady_clock;
uint64_t elapsed_ns(Clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start).count();
}

void cpu_scan(const float *source, float *staging,
              uint32_t rows, uint32_t width, std::vector<uint32_t> &result) {
    std::memcpy(staging, source, size_t(rows) * width * sizeof(float));
    for (uint32_t row = 0; row < rows; ++row) {
        float best = -std::numeric_limits<float>::infinity();
        uint32_t index = kInvalid;
        bool invalid = false;
        for (uint32_t col = 0; col < width; ++col) {
            float value = staging[size_t(row) * width + col];
            if (!std::isfinite(value)) invalid = true;
            else if (value > best || (value == best && col < index)) {
                best = value;
                index = col;
            }
        }
        result[row] = invalid ? kInvalid : index;
    }
}

struct GpuResult {
    uint64_t wall_ns;
    uint64_t gpu_ns;
    std::vector<uint32_t> ids;
};

GpuResult gpu_scan(id<MTLCommandQueue> queue, id<MTLComputePipelineState> first,
                   id<MTLComputePipelineState> second, id<MTLBuffer> input,
                   id<MTLBuffer> parts, id<MTLBuffer> output,
                   uint32_t rows, uint32_t width) {
    @autoreleasepool {
        uint32_t groups = (width + kTile - 1) / kTile;
        auto start = Clock::now();
        id<MTLCommandBuffer> command = [queue commandBuffer];
        if (command == nil) throw std::runtime_error("Metal command allocation failed");
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        if (encoder == nil) throw std::runtime_error("Metal encoder allocation failed");
        [encoder setComputePipelineState:first];
        [encoder setBuffer:input offset:0 atIndex:0];
        [encoder setBuffer:parts offset:0 atIndex:1];
        [encoder setBytes:&width length:sizeof(width) atIndex:2];
        [encoder setBytes:&groups length:sizeof(groups) atIndex:3];
        [encoder dispatchThreadgroups:MTLSizeMake(groups, rows, 1)
                threadsPerThreadgroup:MTLSizeMake(kThreads, 1, 1)];
        [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
        [encoder setComputePipelineState:second];
        [encoder setBuffer:parts offset:0 atIndex:0];
        [encoder setBuffer:output offset:0 atIndex:1];
        [encoder setBytes:&groups length:sizeof(groups) atIndex:2];
        [encoder dispatchThreadgroups:MTLSizeMake(rows, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(kThreads, 1, 1)];
        [encoder endEncoding];
        [command commit];
        [command waitUntilCompleted];
        uint64_t wall = elapsed_ns(start);
        if (command.status != MTLCommandBufferStatusCompleted)
            throw std::runtime_error("Metal command failed");
        double interval = command.GPUEndTime - command.GPUStartTime;
        uint64_t gpu = interval > 0 ? uint64_t(interval * 1e9) : 0;
        auto *values = static_cast<const uint32_t *>(output.contents);
        return {wall, gpu, std::vector<uint32_t>(values, values + rows)};
    }
}

void require_equal(const std::vector<uint32_t> &a, const std::vector<uint32_t> &b) {
    if (a != b) throw std::runtime_error("CPU and Metal greedy IDs differ");
}

void print_ids(const std::vector<uint32_t> &ids) {
    std::cout << '[';
    for (size_t i = 0; i < ids.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << ids[i];
    }
    std::cout << ']';
}

void check_case(id<MTLDevice> device, id<MTLCommandQueue> queue,
                id<MTLComputePipelineState> first, id<MTLComputePipelineState> second,
                const std::vector<float> &values, uint32_t rows, uint32_t width,
                const std::vector<uint32_t> &expected) {
    uint32_t groups = (width + kTile - 1) / kTile;
    id<MTLBuffer> input = [device newBufferWithBytes:values.data()
        length:values.size() * sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> parts = [device newBufferWithLength:size_t(rows) * groups * 12
        options:MTLResourceStorageModeShared];
    id<MTLBuffer> output = [device newBufferWithLength:size_t(rows) * sizeof(uint32_t)
        options:MTLResourceStorageModeShared];
    if (input == nil || parts == nil || output == nil) throw std::runtime_error("Metal buffer failed");
    std::vector<float> staging(values.size());
    std::vector<uint32_t> cpu(rows);
    cpu_scan(static_cast<const float *>(input.contents), staging.data(), rows, width, cpu);
    auto gpu = gpu_scan(queue, first, second, input, parts, output, rows, width);
    require_equal(cpu, expected);
    require_equal(gpu.ids, expected);
}

uint32_t parse_positive(const char *raw, uint32_t maximum) {
    std::string text(raw);
    if (text.empty() || text.find_first_not_of("0123456789") != std::string::npos)
        throw std::runtime_error("invalid numeric argument");
    unsigned long value = std::stoul(text);
    if (value < 1 || value > maximum) throw std::runtime_error("numeric argument outside bound");
    return uint32_t(value);
}
}  // namespace

int main(int argc, char **argv) {
    @autoreleasepool {
        try {
            if (argc != 6) throw std::runtime_error("usage: bench-native-metal-target-greedy CAPTURE ROWS WIDTH REPEATS PAIRS");
            uint32_t rows = parse_positive(argv[2], 16);
            uint32_t width = parse_positive(argv[3], 1048576);
            uint32_t repeats = parse_positive(argv[4], 1000);
            uint32_t pairs = parse_positive(argv[5], 20);
            uint32_t groups = (width + kTile - 1) / kTile;
            size_t scratch_bytes = size_t(rows) * groups * 12 + size_t(rows) * sizeof(uint32_t);
            if (scratch_bytes > 16384) throw std::runtime_error("scratch ceiling exceeded");
            std::ifstream file(argv[1], std::ios::binary | std::ios::ate);
            if (!file) throw std::runtime_error("capture open failed");
            size_t bytes = size_t(rows) * width * sizeof(float);
            if (size_t(file.tellg()) != bytes) throw std::runtime_error("capture extent changed");
            std::vector<float> values(size_t(rows) * width);
            file.seekg(0);
            file.read(reinterpret_cast<char *>(values.data()), bytes);
            if (!file) throw std::runtime_error("capture read failed");

            id<MTLDevice> device = MTLCreateSystemDefaultDevice();
            if (device == nil) throw std::runtime_error("Metal device unavailable");
            id<MTLCommandQueue> queue = [device newCommandQueue];
            NSError *error = nil;
            id<MTLLibrary> library = [device newLibraryWithSource:
                [NSString stringWithUTF8String:kTargetGreedyShader] options:nil error:&error];
            if (library == nil) throw std::runtime_error("Metal shader compile failed");
            id<MTLComputePipelineState> first = [device newComputePipelineStateWithFunction:
                [library newFunctionWithName:@"partial"] error:&error];
            id<MTLComputePipelineState> second = [device newComputePipelineStateWithFunction:
                [library newFunctionWithName:@"finish"] error:&error];
            if (queue == nil || first == nil || second == nil
                || first.maxTotalThreadsPerThreadgroup < kThreads
                || second.maxTotalThreadsPerThreadgroup < kThreads)
                throw std::runtime_error("Metal pipeline admission failed");

            std::vector<float> synthetic(4 * 1031, -10.0f);
            synthetic[7] = synthetic[1010] = 50.0f;
            synthetic[1031 + 1030] = 40.0f;
            synthetic[2 * 1031] = 30.0f;
            synthetic[3 * 1031 + 512] = 20.0f;
            check_case(device, queue, first, second, synthetic, 4, 1031,
                       {7, 1030, 0, 512});
            synthetic[1031 + 500] = NAN;
            synthetic[3 * 1031 + 1029] = INFINITY;
            check_case(device, queue, first, second, synthetic, 4, 1031,
                       {7, kInvalid, 0, kInvalid});

            id<MTLBuffer> input = [device newBufferWithBytes:values.data() length:bytes
                options:MTLResourceStorageModeShared];
            id<MTLBuffer> parts = [device newBufferWithLength:size_t(rows) * groups * 12
                options:MTLResourceStorageModeShared];
            id<MTLBuffer> output = [device newBufferWithLength:size_t(rows) * sizeof(uint32_t)
                options:MTLResourceStorageModeShared];
            if (input == nil || parts == nil || output == nil)
                throw std::runtime_error("Metal measured buffer failed");
            std::vector<float> staging(values.size());
            std::vector<uint32_t> expected(rows);
            cpu_scan(static_cast<const float *>(input.contents), staging.data(),
                     rows, width, expected);
            require_equal(expected, gpu_scan(queue, first, second, input, parts, output,
                                             rows, width).ids);
            for (int warm = 0; warm < 12; ++warm) {
                std::vector<uint32_t> cpu(rows);
                cpu_scan(static_cast<const float *>(input.contents), staging.data(),
                         rows, width, cpu);
                auto gpu = gpu_scan(queue, first, second, input, parts, output,
                                    rows, width);
                require_equal(cpu, expected);
                require_equal(gpu.ids, expected);
            }
            std::cout << "{\"schema_version\":1,\"device\":\""
                      << device.name.UTF8String << "\",\"rows\":" << rows
                      << ",\"width\":" << width << ",\"repeats\":" << repeats
                      << ",\"scratch_bytes\":" << scratch_bytes << ",\"greedy_ids\":";
            print_ids(expected);
            std::cout << ",\"pairs\":[";
            for (uint32_t pair = 0; pair < pairs; ++pair) {
                uint64_t cpu_ns = 0, gpu_ns = 0, gpu_interval_ns = 0;
                std::vector<uint32_t> ids(rows);
                auto run_cpu = [&] {
                    for (uint32_t i = 0; i < repeats; ++i) {
                        auto start = Clock::now();
                        cpu_scan(static_cast<const float *>(input.contents),
                                 staging.data(), rows, width, ids);
                        cpu_ns += elapsed_ns(start);
                        require_equal(ids, expected);
                    }
                };
                auto run_gpu = [&] {
                    for (uint32_t i = 0; i < repeats; ++i) {
                        auto sample = gpu_scan(queue, first, second, input, parts, output,
                                               rows, width);
                        gpu_ns += sample.wall_ns;
                        gpu_interval_ns += sample.gpu_ns;
                        require_equal(sample.ids, expected);
                    }
                };
                if (pair % 2 == 0) { run_cpu(); run_gpu(); }
                else { run_gpu(); run_cpu(); }
                if (pair) std::cout << ',';
                std::cout << "{\"order\":\"" << (pair % 2 == 0 ? "cpu,gpu" : "gpu,cpu")
                          << "\",\"cpu_copy_scan_ns\":" << cpu_ns
                          << ",\"gpu_submit_finish_ns\":" << gpu_ns
                          << ",\"gpu_interval_ns\":" << gpu_interval_ns << '}';
            }
            std::cout << "]}\n";
            return 0;
        } catch (const std::exception &error) {
            std::cerr << error.what() << '\n';
            return 2;
        }
    }
}
