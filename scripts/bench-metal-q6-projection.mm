// Independent, actual-weight Q6_K projection experiment; not a runtime backend.
// Build: clang++ -O3 -std=c++17 -fobjc-arc -framework Foundation -framework Metal \
//   -I GGML/ggml/include -L BUNDLE -Wl,-rpath,BUNDLE -lggml -lggml-base \
//   scripts/bench-metal-q6-projection.mm -o bench-metal-q6-projection
// Run: bench-metal-q6-projection PLUGIN CAPTURE_DIR [--check-only] [--gpu-trace]
// Optional GPU tracing uses the same private commit hook as the repository's
// existing Metal diagnostic. Its wall times are explicitly instrumented.
// The kernel's mapping/arithmetic derive from ggml at
// bb4caa7540188872173c44d161602d9271386413, ggml-metal.metal:8750.
//
// MIT License
// Copyright (c) 2023-2026 The ggml authors
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
// of the Software, and to permit persons to whom the Software is furnished to do
// so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include "ggml.h"
#include "ggml-backend.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <utility>
#include <vector>

static constexpr int PAIRS = 5, ITERATIONS = 20, WARMUPS = 12;
static constexpr double ABS_BOUND = 0.01;

static const char *kernel_source = R"METAL(
#include <metal_stdlib>
using namespace metal;
struct Q6Block { uchar ql[128]; uchar qh[64]; char scales[16]; half d; };
static_assert(sizeof(Q6Block) == 210, "unexpected Q6_K block layout");
kernel void q6_pair_load(
    device const Q6Block *weights [[buffer(0)]],
    device const float *input [[buffer(1)]],
    device float *output [[buffer(2)]],
    constant uint &width [[buffer(3)]],
    constant uint &rows [[buffer(4)]],
    uint group [[threadgroup_position_in_grid]],
    ushort lane [[thread_index_in_simdgroup]],
    ushort simd [[simdgroup_index_in_threadgroup]]) {
    const uint first_row = (group * 2 + simd) * 2;
    if (first_row >= rows) return;
    const uint blocks = width / 256;
    const ushort tid = lane / 2, ix = lane % 2;
    const ushort ip = tid / 8, l0 = 4 * (tid % 8), is = 8 * ip + l0 / 16;
    float sum[2] = {0.0f, 0.0f};
    for (uint block = ix; block < blocks; block += 2) {
        float yl[16];
        device const float *y = input + block * 256 + 128 * ip + l0;
        for (ushort l = 0; l < 4; ++l) {
            yl[4*l + 0] = y[l]; yl[4*l + 1] = y[l + 32];
            yl[4*l + 2] = y[l + 64]; yl[4*l + 3] = y[l + 96];
        }
        for (ushort row = 0; row < 2; ++row) {
            if (first_row + row >= rows) continue;
            device const Q6Block &q = weights[(first_row + row) * blocks + block];
            // All addresses are at least 2-byte aligned, including odd blocks.
            device const ushort *lo1 = (device const ushort *)(q.ql + 64 * ip + l0);
            device const ushort *lo2 = (device const ushort *)(q.ql + 64 * ip + l0 + 32);
            device const ushort *high = (device const ushort *)(q.qh + 32 * ip + l0);
            const ushort a[2] = {lo1[0], lo1[1]};
            const ushort b[2] = {lo2[0], lo2[1]};
            const ushort h[2] = {high[0], high[1]};
            float4 sums = {0.f, 0.f, 0.f, 0.f};
            #pragma unroll
            for (ushort l = 0; l < 4; ++l) {
                const uchar q1 = uchar(a[l / 2] >> (8 * (l % 2)));
                const uchar q2 = uchar(b[l / 2] >> (8 * (l % 2)));
                const uchar qh = uchar(h[l / 2] >> (8 * (l % 2)));
                sums[0] += yl[4*l + 0] * (char((q1 & 0x0f) | ((qh & 0x03) << 4)) - 32);
                sums[1] += yl[4*l + 1] * (char((q2 & 0x0f) | ((qh & 0x0c) << 2)) - 32);
                sums[2] += yl[4*l + 2] * (char((q1 >> 4) | (qh & 0x30)) - 32);
                sums[3] += yl[4*l + 3] * (char((q2 >> 4) | ((qh & 0xc0) >> 2)) - 32);
            }
            sum[row] += q.d * (sums[0] * q.scales[is] + sums[1] * q.scales[is+2] +
                              sums[2] * q.scales[is+4] + sums[3] * q.scales[is+6]);
        }
    }
    for (ushort row = 0; row < 2; ++row) {
        float value = simd_sum(sum[row]);
        if (lane == 0 && first_row + row < rows) output[first_row + row] = value;
    }
}

// Four related target activations reuse each compressed block before the next
// block is fetched. Columns remain contiguous in both input and output.
kernel void q6_batch4(
    device const Q6Block *weights [[buffer(0)]],
    device const float *input [[buffer(1)]],
    device float *output [[buffer(2)]],
    constant uint &width [[buffer(3)]],
    constant uint &rows [[buffer(4)]],
    uint group [[threadgroup_position_in_grid]],
    ushort lane [[thread_index_in_simdgroup]],
    ushort simd [[simdgroup_index_in_threadgroup]]) {
    const uint first_row = (group * 2 + simd) * 2;
    if (first_row >= rows) return;
    const uint blocks = width / 256;
    const ushort tid = lane / 2, ix = lane % 2;
    const ushort ip = tid / 8, l0 = 4 * (tid % 8), is = 8 * ip + l0 / 16;
    float sum[2][4] = {};
    for (uint block = ix; block < blocks; block += 2) {
        const uint input_offset = block * 256 + 128 * ip + l0;
        for (ushort row = 0; row < 2; ++row) {
            if (first_row + row >= rows) continue;
            device const Q6Block &q = weights[(first_row + row) * blocks + block];
            device const ushort *lo1 = (device const ushort *)(q.ql + 64 * ip + l0);
            device const ushort *lo2 = (device const ushort *)(q.ql + 64 * ip + l0 + 32);
            device const ushort *high = (device const ushort *)(q.qh + 32 * ip + l0);
            const ushort a[2] = {lo1[0], lo1[1]};
            const ushort b[2] = {lo2[0], lo2[1]};
            const ushort h[2] = {high[0], high[1]};
            float4 sums[4] = {};
            #pragma unroll
            for (ushort l = 0; l < 4; ++l) {
                const uchar q1 = uchar(a[l / 2] >> (8 * (l % 2)));
                const uchar q2 = uchar(b[l / 2] >> (8 * (l % 2)));
                const uchar qh = uchar(h[l / 2] >> (8 * (l % 2)));
                const float v0 = char((q1 & 0x0f) | ((qh & 0x03) << 4)) - 32;
                const float v1 = char((q2 & 0x0f) | ((qh & 0x0c) << 2)) - 32;
                const float v2 = char((q1 >> 4) | (qh & 0x30)) - 32;
                const float v3 = char((q2 >> 4) | ((qh & 0xc0) >> 2)) - 32;
                for (ushort col = 0; col < 4; ++col) {
                    device const float *y = input + col * width + input_offset;
                    sums[col][0] += y[l] * v0;
                    sums[col][1] += y[l + 32] * v1;
                    sums[col][2] += y[l + 64] * v2;
                    sums[col][3] += y[l + 96] * v3;
                }
            }
            for (ushort col = 0; col < 4; ++col) {
                sum[row][col] += q.d *
                    (sums[col][0] * q.scales[is] + sums[col][1] * q.scales[is+2] +
                     sums[col][2] * q.scales[is+4] + sums[col][3] * q.scales[is+6]);
            }
        }
    }
    for (ushort row = 0; row < 2; ++row) {
        for (ushort col = 0; col < 4; ++col) {
            float value = simd_sum(sum[row][col]);
            if (lane == 0 && first_row + row < rows)
                output[col * rows + first_row + row] = value;
        }
    }
}

// Experimental producer-side greedy path. It keeps the paired Q6_K arithmetic
// above and replaces four full logits per threadgroup with one candidate.
struct TopPart { float value; uint index; uint invalid; };
kernel void q6_pair_top(
    device const Q6Block *weights [[buffer(0)]],
    device const float *input [[buffer(1)]],
    device TopPart *parts [[buffer(2)]],
    constant uint &width [[buffer(3)]],
    constant uint &rows [[buffer(4)]],
    uint group [[threadgroup_position_in_grid]],
    ushort lane [[thread_index_in_simdgroup]],
    ushort simd [[simdgroup_index_in_threadgroup]],
    ushort thread_index [[thread_index_in_threadgroup]]) {
    const uint first_row = (group * 2 + simd) * 2;
    const uint blocks = width / 256;
    const ushort tid = lane / 2, ix = lane % 2;
    const ushort ip = tid / 8, l0 = 4 * (tid % 8), is = 8 * ip + l0 / 16;
    float sum[2] = {0.0f, 0.0f};
    for (uint block = ix; block < blocks; block += 2) {
        float yl[16];
        device const float *y = input + block * 256 + 128 * ip + l0;
        for (ushort l = 0; l < 4; ++l) {
            yl[4*l + 0] = y[l]; yl[4*l + 1] = y[l + 32];
            yl[4*l + 2] = y[l + 64]; yl[4*l + 3] = y[l + 96];
        }
        for (ushort row = 0; row < 2; ++row) {
            if (first_row + row >= rows) continue;
            device const Q6Block &q = weights[(first_row + row) * blocks + block];
            device const ushort *lo1 = (device const ushort *)(q.ql + 64 * ip + l0);
            device const ushort *lo2 = (device const ushort *)(q.ql + 64 * ip + l0 + 32);
            device const ushort *high = (device const ushort *)(q.qh + 32 * ip + l0);
            const ushort a[2] = {lo1[0], lo1[1]};
            const ushort b[2] = {lo2[0], lo2[1]};
            const ushort h[2] = {high[0], high[1]};
            float4 sums = {0.f, 0.f, 0.f, 0.f};
            #pragma unroll
            for (ushort l = 0; l < 4; ++l) {
                const uchar q1 = uchar(a[l / 2] >> (8 * (l % 2)));
                const uchar q2 = uchar(b[l / 2] >> (8 * (l % 2)));
                const uchar qh = uchar(h[l / 2] >> (8 * (l % 2)));
                sums[0] += yl[4*l + 0] * (char((q1 & 0x0f) | ((qh & 0x03) << 4)) - 32);
                sums[1] += yl[4*l + 1] * (char((q2 & 0x0f) | ((qh & 0x0c) << 2)) - 32);
                sums[2] += yl[4*l + 2] * (char((q1 >> 4) | (qh & 0x30)) - 32);
                sums[3] += yl[4*l + 3] * (char((q2 >> 4) | ((qh & 0xc0) >> 2)) - 32);
            }
            sum[row] += q.d * (sums[0] * q.scales[is] + sums[1] * q.scales[is+2] +
                              sums[2] * q.scales[is+4] + sums[3] * q.scales[is+6]);
        }
    }
    threadgroup float values[4];
    threadgroup uint indices[4];
    threadgroup uint invalids[4];
    for (ushort row = 0; row < 2; ++row) {
        const float value = simd_sum(sum[row]);
        if (lane == 0) {
            const uint slot = 2*simd + row;
            const uint index = first_row + row;
            values[slot] = index < rows ? value : -INFINITY;
            indices[slot] = index < rows ? index : 0xffffffffu;
            invalids[slot] = index < rows && !isfinite(value);
        }
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (thread_index == 0) {
        float best = -INFINITY; uint best_index = 0xffffffffu, invalid = 0;
        for (uint j = 0; j < 4; ++j) {
            invalid |= invalids[j];
            if (indices[j] != 0xffffffffu && isfinite(values[j]) &&
                (values[j] > best || (values[j] == best && indices[j] < best_index))) {
                best = values[j]; best_index = indices[j];
            }
        }
        parts[group] = {best, best_index, invalid};
    }
}

kernel void q6_top_finish(
    device const TopPart *parts [[buffer(0)]],
    device uint *result [[buffer(1)]],
    constant uint &count [[buffer(2)]],
    uint tid [[thread_index_in_threadgroup]]) {
    threadgroup float values[256];
    threadgroup uint indices[256];
    threadgroup uint invalids[256];
    float best = -INFINITY; uint index = 0xffffffffu, invalid = 0;
    for (uint j = tid; j < count; j += 256) {
        TopPart part = parts[j];
        invalid |= part.invalid;
        if (part.index != 0xffffffffu &&
            (part.value > best || (part.value == best && part.index < index))) {
            best = part.value; index = part.index;
        }
    }
    values[tid] = best; indices[tid] = index; invalids[tid] = invalid;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = 128; stride > 0; stride >>= 1) {
        if (tid < stride) {
            invalids[tid] |= invalids[tid + stride];
            const float other = values[tid + stride];
            const uint other_index = indices[tid + stride];
            if (other > values[tid] || (other == values[tid] && other_index < indices[tid])) {
                values[tid] = other; indices[tid] = other_index;
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (tid == 0) result[0] = invalids[0] ? 0xffffffffu : indices[0];
}
)METAL";

static void require(bool condition, const char *message) {
    if (!condition) { std::fprintf(stderr, "Q6_PROBE error=%s\n", message); std::exit(1); }
}
static std::string path(const char *dir, const std::string &name) { return std::string(dir) + "/" + name; }
static std::ifstream file(const std::string &name, size_t bytes) {
    std::ifstream stream(name, std::ios::binary | std::ios::ate);
    require(bool(stream) && stream.tellg() == std::streamoff(bytes), "capture file missing or wrong extent");
    stream.seekg(0); return stream;
}
static std::vector<float> floats(const std::string &name, size_t count) {
    auto stream = file(name, count * sizeof(float));
    std::vector<float> result(count);
    stream.read(reinterpret_cast<char *>(result.data()), count * sizeof(float));
    require(bool(stream), "capture read failed");
    for (float v : result) require(std::isfinite(v), "nonfinite capture value");
    return result;
}
static void compare(const float *expected, const float *actual, size_t count,
                    int activation, const char *shape, const char *comparison) {
    double maximum = 0;
    size_t expected_argmax = 0, actual_argmax = 0;
    for (size_t i = 0; i < count; ++i) {
        require(std::isfinite(expected[i]) && std::isfinite(actual[i]), "nonfinite output value");
        double error = std::abs(double(expected[i]) - actual[i]);
        maximum = std::max(maximum, error);
        require(error <= ABS_BOUND, "predeclared 0.01 absolute bound exceeded");
        if (expected[i] > expected[expected_argmax]) expected_argmax = i;
        if (actual[i] > actual[actual_argmax]) actual_argmax = i;
    }
    require(expected_argmax == actual_argmax, "greedy argmax differs");
    std::printf("{\"event\":\"check\",\"activation\":%d,\"shape\":\"%s\",\"comparison\":\"%s\","
                "\"count\":%zu,\"max_abs\":%.9g,\"argmax\":%zu}\n",
                activation, shape, comparison, count, maximum, actual_argmax);
}

static void (*original_commit)(id, SEL);
static NSObject *trace_lock;
static NSMutableArray<id<MTLCommandBuffer>> *trace_commands;
static void recorded_commit(id<MTLCommandBuffer> command, SEL selector) {
    @synchronized(trace_lock) { if (trace_commands) [trace_commands addObject:command]; }
    original_commit(command, selector);
}
static void install_trace() {
    Method method = class_getInstanceMethod(objc_getClass("_MTLCommandBuffer"), @selector(commit));
    require(method != nullptr, "requested GPU command-buffer hook is unavailable");
    trace_lock = [NSObject new];
    original_commit = reinterpret_cast<void (*)(id, SEL)>(method_setImplementation(method, (IMP)recorded_commit));
}
struct Timing { double wall_ms, gpu_ms; size_t commands; };
struct TopPartHost { float value; uint32_t index, invalid; };
static_assert(sizeof(TopPartHost) == 12, "Metal partial ABI changed");
static void begin_trace(bool trace) {
    if (trace) { @synchronized(trace_lock) { trace_commands = [NSMutableArray new]; } }
}
static std::pair<double, size_t> end_trace() {
    NSArray<id<MTLCommandBuffer>> *commands;
    @synchronized(trace_lock) { commands = trace_commands; trace_commands = nil; }
    require(commands.count > 0, "no command buffers captured for a measured invocation");
    std::vector<std::pair<double, double>> intervals;
    for (id<MTLCommandBuffer> command in commands) {
        require(command.status == MTLCommandBufferStatusCompleted, "captured Metal command failed or incomplete");
        double start = command.GPUStartTime, end = command.GPUEndTime;
        require(start > 0 && end > start, "GPU timestamps unavailable");
        intervals.emplace_back(start, end);
    }
    std::sort(intervals.begin(), intervals.end());
    double total = 0, start = intervals[0].first, end = intervals[0].second;
    for (size_t i = 1; i < intervals.size(); ++i) {
        if (intervals[i].first <= end) end = std::max(end, intervals[i].second);
        else { total += end - start; start = intervals[i].first; end = intervals[i].second; }
    }
    return {1000 * (total + end - start), intervals.size()};
}
static std::string optional_ms(double value) {
    if (value < 0) return "null";
    char buffer[64]; std::snprintf(buffer, sizeof(buffer), "%.9f", value); return buffer;
}

int main(int argc, char **argv) {
    require(argc >= 3 && argc <= 7, "usage: bench-metal-q6-projection PLUGIN CAPTURE_DIR [--check-only] [--gpu-trace] [--fused-top] [--batch4]");
    bool check_only = false, trace = false, fused_top = false, batch4 = false;
    for (int i = 3; i < argc; ++i) {
        if (!std::strcmp(argv[i], "--check-only") && !check_only) check_only = true;
        else if (!std::strcmp(argv[i], "--gpu-trace") && !trace) trace = true;
        else if (!std::strcmp(argv[i], "--fused-top") && !fused_top) fused_top = true;
        else if (!std::strcmp(argv[i], "--batch4") && !batch4) batch4 = true;
        else require(false, "unknown or duplicate option");
    }
    require(!(batch4 && fused_top), "batch4 and fused-top are separate screens");
    std::ifstream geometry(path(argv[2], "geometry.txt"));
    std::string version, trailing; uint64_t width64 = 0, rows64 = 0; int type = -1;
    geometry >> version >> width64 >> rows64 >> type;
    require(bool(geometry) && !(geometry >> trailing) && version == "q6-capture-v1" && type == 14 &&
            width64 >= 256 && width64 <= 65536 && width64 % 256 == 0 && rows64 >= 3 &&
            rows64 <= 1048576 && width64 / 256 * rows64 * 210 <= 2147483648ULL,
            "invalid capture geometry");
    std::ifstream completed(path(argv[2], "complete.txt")); int count = 0;
    completed >> count;
    require(bool(completed) && !(completed >> trailing) && count == 3, "incomplete capture set");
    const uint32_t width = uint32_t(width64), rows = uint32_t(rows64);
    const uint32_t tail_rows = rows > 257 ? 257 : rows - 1;
    const size_t weight_bytes = size_t(width / 256) * rows * 210;
    std::vector<float> inputs[3], expected[3];
    int kinds[3];
    for (int i = 0; i < 3; ++i) {
        std::ifstream kind(path(argv[2], std::to_string(i) + "-kind.txt"));
        kind >> kinds[i];
        require(bool(kind) && !(kind >> trailing) &&
                (i == 0 ? kinds[i] == 0 : kinds[i] == 1 || kinds[i] == 2), "unexpected capture phase");
        inputs[i] = floats(path(argv[2], std::to_string(i) + "-input.bin"), width);
        expected[i] = floats(path(argv[2], std::to_string(i) + "-output.bin"), rows);
    }
    @autoreleasepool {
        auto reg = ggml_backend_load(argv[1]); require(reg, "pinned Metal plugin load failed");
        auto backend = ggml_backend_dev_init(ggml_backend_reg_dev_get(reg, 0), nullptr);
        require(backend, "ggml device initialization failed");
        auto ctx = ggml_init({ggml_tensor_overhead() * 40 + 2 * ggml_graph_overhead_custom(16, false), nullptr, true});
        require(ctx, "ggml context initialization failed");
        auto w = ggml_new_tensor_2d(ctx, GGML_TYPE_Q6_K, width, rows);
        auto x = batch4 ? ggml_new_tensor_2d(ctx, GGML_TYPE_F32, width, 4)
                        : ggml_new_tensor_1d(ctx, GGML_TYPE_F32, width);
        auto tail_w = ggml_view_2d(ctx, w, width, tail_rows, w->nb[1], 0);
        ggml_tensor *outputs[2] = {ggml_mul_mat(ctx, w, x), ggml_mul_mat(ctx, tail_w, x)};
        ggml_tensor *choices[2] = {nullptr, nullptr};
        ggml_cgraph *graphs[2];
        for (int i = 0; i < 2; ++i) {
            if (fused_top) choices[i] = ggml_argmax(ctx, outputs[i]);
            graphs[i] = ggml_new_graph_custom(ctx, 16, false);
            ggml_build_forward_expand(graphs[i], fused_top ? choices[i] : outputs[i]);
        }
        auto buffer = ggml_backend_alloc_ctx_tensors(ctx, backend); require(buffer, "ggml allocation failed");
        require(ggml_nbytes(w) == weight_bytes, "Q6_K layout disagrees with capture");

        id<MTLDevice> metal = MTLCreateSystemDefaultDevice(); require(metal != nil, "Metal device unavailable");
        NSError *error = nil;
        id<MTLLibrary> library = [metal newLibraryWithSource:[NSString stringWithUTF8String:kernel_source]
                                                   options:nil error:&error];
        if (!library) std::fprintf(stderr, "Metal compile: %s\n", error.localizedDescription.UTF8String);
        require(library != nil, "native kernel compilation failed");
        id<MTLComputePipelineState> pipeline = [metal newComputePipelineStateWithFunction:
            [library newFunctionWithName:batch4 ? @"q6_batch4" : @"q6_pair_load"] error:&error];
        require(pipeline != nil && pipeline.threadExecutionWidth == 32 && pipeline.maxTotalThreadsPerThreadgroup >= 64,
                "native pipeline geometry unavailable");
        id<MTLComputePipelineState> top_pipeline = nil, finish_pipeline = nil;
        if (fused_top) {
            top_pipeline = [metal newComputePipelineStateWithFunction:
                [library newFunctionWithName:@"q6_pair_top"] error:&error];
            finish_pipeline = [metal newComputePipelineStateWithFunction:
                [library newFunctionWithName:@"q6_top_finish"] error:&error];
            require(top_pipeline != nil && top_pipeline.threadExecutionWidth == 32 &&
                    top_pipeline.maxTotalThreadsPerThreadgroup >= 64 && finish_pipeline != nil &&
                    finish_pipeline.maxTotalThreadsPerThreadgroup >= 256,
                    "fused top pipeline geometry unavailable");
        }
        id<MTLCommandQueue> queue = [metal newCommandQueue];
        id<MTLBuffer> mw = [metal newBufferWithLength:weight_bytes options:MTLResourceStorageModeShared];
        id<MTLBuffer> mx = [metal newBufferWithLength:size_t(width) * 4 * (batch4 ? 4 : 1)
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> my = fused_top ? nil : [metal newBufferWithLength:size_t(rows) * 4 * (batch4 ? 4 : 1)
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> parts = fused_top ? [metal newBufferWithLength:size_t((rows + 3) / 4) * 12
            options:MTLResourceStorageModeShared] : nil;
        id<MTLBuffer> token = fused_top ? [metal newBufferWithLength:4 options:MTLResourceStorageModeShared] : nil;
        require(queue && mw && mx && (fused_top ? (parts != nil && token != nil) : my != nil),
                "native allocation failed");
        auto weights = file(path(argv[2], "weights.bin"), weight_bytes);
        for (size_t offset = 0; offset < weight_bytes;) {
            size_t bytes = std::min(size_t(1024 * 1024), weight_bytes - offset);
            auto destination = static_cast<char *>(mw.contents) + offset;
            weights.read(destination, bytes); require(bool(weights), "weight read failed");
            ggml_backend_tensor_set(w, destination, offset, bytes);
            offset += bytes;
        }
        if (trace) install_trace();
        std::printf("{\"event\":\"setup\",\"width\":%u,\"rows\":%u,\"tail_rows\":%u,\"weight_bytes\":%zu,"
                    "\"ggml_buffer_bytes\":%zu,\"native_buffer_bytes\":%zu,\"simd_width\":%lu,"
                    "\"threads\":64,\"pipeline_max_threads\":%lu,\"fused_top\":%s,\"batch4\":%s,\"wall_instrumented\":%s,"
                    "\"warmups\":%d,\"pairs\":%d,\"iterations_per_pair\":%d}\n", width, rows, tail_rows,
                    weight_bytes, ggml_backend_buffer_get_size(buffer), weight_bytes +
                    size_t(width) * 4 * (batch4 ? 4 : 1) +
                    (fused_top ? size_t((rows + 3) / 4) * 12 + 4
                               : size_t(rows) * 4 * (batch4 ? 4 : 1)),
                    (unsigned long)pipeline.threadExecutionWidth, (unsigned long)pipeline.maxTotalThreadsPerThreadgroup,
                    fused_top ? "true" : "false", batch4 ? "true" : "false",
                    trace ? "true" : "false", WARMUPS, PAIRS, ITERATIONS);
        auto run = [&](int arm, int shape) -> Timing {
            begin_trace(trace);
            auto start = std::chrono::steady_clock::now();
            double gpu = -1; size_t command_count = 0;
            id<MTLCommandBuffer> command = nil;
            if (arm == 0) {
                require(ggml_backend_graph_compute(backend, graphs[shape]) == GGML_STATUS_SUCCESS, "ggml compute failed");
                if (fused_top) {
                    int32_t selected = -1;
                    ggml_backend_tensor_get(choices[shape], &selected, 0, sizeof(selected));
                    require(selected >= 0 && selected < (shape == 0 ? rows : tail_rows), "ggml argmax invalid");
                }
            } else {
                command = [queue commandBuffer];
                id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
                require(command && encoder, "native command allocation failed");
                uint32_t active_rows = shape == 0 ? rows : tail_rows;
                [encoder setComputePipelineState:fused_top ? top_pipeline : pipeline];
                [encoder setBuffer:mw offset:0 atIndex:0]; [encoder setBuffer:mx offset:0 atIndex:1];
                [encoder setBuffer:fused_top ? parts : my offset:0 atIndex:2];
                [encoder setBytes:&width length:sizeof(width) atIndex:3];
                [encoder setBytes:&active_rows length:sizeof(active_rows) atIndex:4];
                [encoder dispatchThreadgroups:MTLSizeMake((active_rows + 3) / 4, 1, 1)
                         threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
                if (fused_top) {
                    uint32_t groups = (active_rows + 3) / 4;
                    [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
                    [encoder setComputePipelineState:finish_pipeline];
                    [encoder setBuffer:parts offset:0 atIndex:0];
                    [encoder setBuffer:token offset:0 atIndex:1];
                    [encoder setBytes:&groups length:sizeof(groups) atIndex:2];
                    [encoder dispatchThreadgroups:MTLSizeMake(1, 1, 1)
                             threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
                }
                [encoder endEncoding]; [command commit]; [command waitUntilCompleted];
                require(command.status == MTLCommandBufferStatusCompleted, "native command failed");
                if (fused_top) require(*static_cast<uint32_t *>(token.contents) < active_rows,
                                       "fused top output invalid");
            }
            double wall = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();
            if (trace) {
                auto timing = end_trace(); gpu = timing.first; command_count = timing.second;
            } else if (command) {
                if (command.GPUStartTime > 0 && command.GPUEndTime > command.GPUStartTime)
                    gpu = 1000 * (command.GPUEndTime - command.GPUStartTime);
                command_count = 1;
            }
            return {wall, gpu, command_count};
        };
        auto input = [&](int activation) {
            for (int col = 0; col < (batch4 ? 4 : 1); ++col) {
                const float *values = inputs[batch4 ? col % 3 : activation].data();
                const size_t offset = size_t(col) * width * sizeof(float);
                ggml_backend_tensor_set(x, values, offset, size_t(width) * sizeof(float));
                std::memcpy(static_cast<char *>(mx.contents) + offset, values,
                            size_t(width) * sizeof(float));
            }
        };
        // Every full-vector and tail qualification completes before any timing.
        for (int activation = 0; activation < (batch4 ? 1 : 3); ++activation) {
            input(activation);
            for (int shape = 0; shape < 2; ++shape) {
                run(0, shape); run(1, shape);
                size_t n = shape == 0 ? rows : tail_rows;
                std::vector<float> reference(n * (batch4 ? 4 : 1));
                ggml_backend_tensor_get(outputs[shape], reference.data(), 0,
                                        reference.size() * sizeof(float));
                const char *label = shape == 0 ? "full" : "tail";
                for (int col = 0; col < (batch4 ? 4 : 1); ++col) {
                    const int source = batch4 ? col % 3 : activation;
                    compare(expected[source].data(), reference.data() + col * n, n,
                            source, label, "captured_vs_ggml");
                }
                if (fused_top) {
                    int32_t reference_top = -1;
                    ggml_backend_tensor_get(choices[shape], &reference_top, 0, sizeof(reference_top));
                    size_t expected_top = 0;
                    for (size_t row = 1; row < n; ++row) {
                        if (expected[activation][row] > expected[activation][expected_top]) expected_top = row;
                    }
                    require(reference_top == int32_t(expected_top) &&
                            *static_cast<uint32_t *>(token.contents) == expected_top,
                            "fused top differs from full-logit oracle");
                    std::printf("{\"event\":\"top_check\",\"activation\":%d,\"shape\":\"%s\",\"token\":%zu}\n",
                                activation, label, expected_top);
                } else {
                    for (int col = 0; col < (batch4 ? 4 : 1); ++col) {
                        compare(reference.data() + col * n,
                                static_cast<const float *>(my.contents) + col * n, n,
                                batch4 ? col % 3 : activation, label, "ggml_vs_native");
                    }
                    if (batch4) {
                        std::printf("{\"event\":\"batch4_check\",\"shape\":\"%s\","
                                    "\"tokens\":[", label);
                        for (int col = 0; col < 4; ++col) {
                            const float *column = reference.data() + col * n;
                            size_t top = 0;
                            for (size_t row = 1; row < n; ++row)
                                if (column[row] > column[top]) top = row;
                            std::printf("%s%zu", col ? "," : "", top);
                        }
                        std::printf("]}\n");
                    }
                }
            }
        }
        if (fused_top) {
            // The data-path buffer can contain only one partial for a valid
            // three- or four-row capture; edge cases always need two entries.
            id<MTLBuffer> edge_parts = [metal newBufferWithLength:2 * sizeof(TopPartHost)
                options:MTLResourceStorageModeShared];
            require(edge_parts != nil, "final-reduction check allocation failed");
            auto partial = static_cast<TopPartHost *>(edge_parts.contents);
            partial[0] = {10.0f, 4, 0}; partial[1] = {10.0f, 3, 0};
            auto check_finish = [&]() -> uint32_t {
                uint32_t groups = 2;
                id<MTLCommandBuffer> command = [queue commandBuffer];
                id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
                require(command && encoder, "final-reduction check allocation failed");
                [encoder setComputePipelineState:finish_pipeline];
                [encoder setBuffer:edge_parts offset:0 atIndex:0];
                [encoder setBuffer:token offset:0 atIndex:1];
                [encoder setBytes:&groups length:sizeof(groups) atIndex:2];
                [encoder dispatchThreadgroups:MTLSizeMake(1, 1, 1)
                         threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
                [encoder endEncoding]; [command commit]; [command waitUntilCompleted];
                require(command.status == MTLCommandBufferStatusCompleted,
                        "final-reduction check failed");
                return *static_cast<uint32_t *>(token.contents);
            };
            require(check_finish() == 3, "final-reduction first-index tie failed");
            partial[1].invalid = 1;
            require(check_finish() == 0xffffffffu, "final-reduction nonfinite refusal failed");
            std::printf("{\"event\":\"top_edge_check\",\"tie\":3,\"nonfinite_refused\":true}\n");
        }
        if (!check_only) for (int activation = 0; activation < (batch4 ? 1 : 3); ++activation) {
            input(activation);
            for (int i = 0; i < WARMUPS; ++i) { run(0, 0); run(1, 0); }
            for (int pair = 0; pair < PAIRS; ++pair) {
                double walls[2] = {0, 0}, gpus[2] = {0, 0}; bool gpu_present[2] = {true, true};
                for (int iteration = 0; iteration < ITERATIONS; ++iteration) for (int order = 0; order < 2; ++order) {
                    int arm = (pair + order) % 2; Timing t = run(arm, 0);
                    walls[arm] += t.wall_ms;
                    if (t.gpu_ms < 0) gpu_present[arm] = false; else gpus[arm] += t.gpu_ms;
                    std::printf("{\"event\":\"sample\",\"activation\":%d,\"kind\":%d,\"pair\":%d,\"iteration\":%d,"
                                "\"arm\":\"%s\",\"wall_ms\":%.9f,\"gpu_union_ms\":%s,\"commands\":%zu}\n",
                                activation, kinds[activation], pair, iteration,
                                arm ? (fused_top ? "fused_top" : "native") : "ggml",
                                t.wall_ms, optional_ms(t.gpu_ms).c_str(), t.commands);
                }
                std::printf("{\"event\":\"pair\",\"activation\":%d,\"pair\":%d,\"ggml_wall_ms\":%.9f,\"native_wall_ms\":%.9f,"
                            "\"ggml_gpu_union_ms\":%s,\"native_gpu_union_ms\":%s}\n", activation, pair,
                            walls[0]/ITERATIONS, walls[1]/ITERATIONS,
                            optional_ms(gpu_present[0] ? gpus[0]/ITERATIONS : -1).c_str(),
                            optional_ms(gpu_present[1] ? gpus[1]/ITERATIONS : -1).c_str());
            }
        }
        ggml_backend_buffer_free(buffer); ggml_free(ctx); ggml_backend_free(backend);
        std::printf("{\"event\":\"complete\",\"check_only\":%s}\n", check_only ? "true" : "false");
    }
    return 0;
}
