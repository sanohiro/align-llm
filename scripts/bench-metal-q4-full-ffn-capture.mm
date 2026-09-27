// Independent complete Q4_0 FFN screen on actual captured Qwen3.5-2B bytes.
// The Q4_0 packed-dot method follows ggml-metal's mul_vec_q_n_f32_impl.
// This is a developer probe, not an inference runtime.

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <vector>

static constexpr int WIDTH = 2048;
static constexpr int HIDDEN = 6144;
static constexpr int ITERATIONS = 20;
static constexpr int PAIRS = 5;

static const char * kernel_source = R"METAL(
#include <metal_stdlib>
using namespace metal;

struct Q40Block { half scale; uchar packed[16]; };

inline float q40_dot(device const Q40Block * weight, float sum_x,
                     thread float * scaled_x, uint half_lane) {
    device const ushort * packed = (device const ushort *)weight->packed + half_lane * 4;
    float accum = 0.0f;
    for (uint i = 0; i < 4; ++i) {
        ushort q = packed[i];
        accum += scaled_x[i * 2] * float(q & 0x000f);
        accum += scaled_x[i * 2 + 1] * float(q & 0x0f00);
        accum += scaled_x[i * 2 + 8] * float(q & 0x00f0);
        accum += scaled_x[i * 2 + 9] * float(q & 0xf000);
    }
    return float(weight->scale) * (accum - 8.0f * sum_x);
}

kernel void q40_gate_up_swiglu(
    device const Q40Block * gate_weight [[buffer(0)]],
    device const Q40Block * up_weight [[buffer(1)]],
    device const float * input [[buffer(2)]],
    device float * gated [[buffer(3)]],
    uint tid [[thread_position_in_grid]]) {
    uint row = (tid / 32) * 4;
    if (row >= 6144) return;
    uint lane = tid % 32;
    uint block_lane = lane / 2;
    uint half_lane = lane % 2;
    float gate[4] = {0}, up[4] = {0};
    for (uint block = block_lane; block < 2048 / 32; block += 16) {
        float scaled_x[16], sum_x = 0.0f;
        uint at = block * 32 + half_lane * 8;
        for (uint i = 0; i < 8; i += 2) {
            float a = input[at + i], b = input[at + i + 1];
            float c = input[at + i + 16], d = input[at + i + 17];
            sum_x += a + b + c + d;
            scaled_x[i] = a;
            scaled_x[i + 1] = b / 256.0f;
            scaled_x[i + 8] = c / 16.0f;
            scaled_x[i + 9] = d / 4096.0f;
        }
        for (uint r = 0; r < 4; ++r) {
            gate[r] += q40_dot(gate_weight + (row + r) * (2048 / 32) + block,
                               sum_x, scaled_x, half_lane);
            up[r] += q40_dot(up_weight + (row + r) * (2048 / 32) + block,
                             sum_x, scaled_x, half_lane);
        }
    }
    for (uint r = 0; r < 4; ++r) {
        float g = simd_sum(gate[r]), u = simd_sum(up[r]);
        if (lane == 0) gated[row + r] = (g / (1.0f + exp(-g))) * u;
    }
}

kernel void q40_down(
    device const Q40Block * weights [[buffer(0)]],
    device const float * input [[buffer(1)]],
    device float * output [[buffer(2)]],
    uint tid [[thread_position_in_grid]]) {
    uint row = (tid / 32) * 4;
    if (row >= 2048) return;
    uint lane = tid % 32;
    uint block_lane = lane / 2;
    uint half_lane = lane % 2;
    float value[4] = {0};
    for (uint block = block_lane; block < 6144 / 32; block += 16) {
        float scaled_x[16], sum_x = 0.0f;
        uint at = block * 32 + half_lane * 8;
        for (uint i = 0; i < 8; i += 2) {
            float a = input[at + i], b = input[at + i + 1];
            float c = input[at + i + 16], d = input[at + i + 17];
            sum_x += a + b + c + d;
            scaled_x[i] = a;
            scaled_x[i + 1] = b / 256.0f;
            scaled_x[i + 8] = c / 16.0f;
            scaled_x[i + 9] = d / 4096.0f;
        }
        for (uint r = 0; r < 4; ++r) {
            value[r] += q40_dot(weights + (row + r) * (6144 / 32) + block,
                                sum_x, scaled_x, half_lane);
        }
    }
    for (uint r = 0; r < 4; ++r) {
        float total = simd_sum(value[r]);
        if (lane == 0) output[row + r] = total;
    }
}
)METAL";

static void fail(const char * reason) {
    std::fprintf(stderr, "%s\n", reason);
    std::exit(1);
}

static std::vector<uint8_t> capture(const char *root, int layer,
                                    const char *role, size_t bytes) {
    char path[4096];
    int length = std::snprintf(path, sizeof(path), "%s/%02d-%s.bin", root, layer, role);
    if (length < 0 || length >= int(sizeof(path))) fail("capture path too long");
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    if (!file || file.tellg() != std::streamoff(bytes)) fail("capture size mismatch");
    std::vector<uint8_t> data(bytes);
    file.seekg(0);
    file.read(reinterpret_cast<char *>(data.data()), bytes);
    if (!file) fail("capture read failed");
    return data;
}

static void check_capture(ggml_tensor *tensor, const std::vector<uint8_t> &bytes) {
    std::vector<uint8_t> rebuilt(bytes.size());
    ggml_backend_tensor_get(tensor, rebuilt.data(), 0, rebuilt.size());
    if (std::memcmp(rebuilt.data(), bytes.data(), bytes.size()) != 0)
        fail("captured and rebuilt ggml outputs differ");
}

static double elapsed_ms(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count();
}

static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

struct Sample { double wall_ms, gpu_ms; };

static float check_output(ggml_tensor * tensor,
                          id<MTLBuffer> actual_buffer, int count, const char * label) {
    std::vector<float> expected(count);
    ggml_backend_tensor_get(tensor, expected.data(), 0, count * sizeof(float));
    const float * actual = static_cast<const float *>(actual_buffer.contents);
    float max_abs = 0;
    for (int i = 0; i < count; ++i) {
        float diff = std::fabs(expected[i] - actual[i]);
        max_abs = std::max(max_abs, diff);
        if (!std::isfinite(expected[i]) || !std::isfinite(actual[i]) ||
            diff > 0.005f + 0.0005f * std::fabs(expected[i])) {
            std::fprintf(stderr, "%s mismatch at %d: ggml=%g native=%g diff=%g\n",
                         label, i, expected[i], actual[i], diff);
            std::exit(1);
        }
    }
    return max_abs;
}

int main(int argc, char ** argv) {
    if (argc < 4 || argc > 5)
        fail("usage: bench-metal-q4-full-ffn-capture LIBGGML_METAL_SO CAPTURE_DIR LAYER [THREADGROUP_SIZE]");
    int layer = std::atoi(argv[3]);
    if (layer != 3 && layer != 23) fail("screen admits only captured layers 3 and 23");
    int group_size = argc == 5 ? std::atoi(argv[4]) : 128;
    if (group_size != 64 && group_size != 128 && group_size != 256)
        fail("THREADGROUP_SIZE must be 64, 128, or 256");
    @autoreleasepool {
        auto setup_start = std::chrono::steady_clock::now();
        ggml_backend_reg_t reg = ggml_backend_load(argv[1]);
        if (!reg) fail("could not load pinned ggml Metal plugin");
        ggml_backend_dev_t dev = ggml_backend_reg_dev_get(reg, 0);
        ggml_backend_t backend = ggml_backend_dev_init(dev, nullptr);
        if (!backend) fail("could not initialize ggml Metal device");
        ggml_init_params params = {
            ggml_tensor_overhead() * 32 + ggml_graph_overhead_custom(32, false),
            nullptr, true
        };
        ggml_context * ctx = ggml_init(params);
        if (!ctx) fail("could not initialize ggml context");
        ggml_tensor * wg = ggml_new_tensor_2d(ctx, GGML_TYPE_Q4_0, WIDTH, HIDDEN);
        ggml_tensor * wu = ggml_new_tensor_2d(ctx, GGML_TYPE_Q4_0, WIDTH, HIDDEN);
        ggml_tensor * wd = ggml_new_tensor_2d(ctx, GGML_TYPE_Q4_0, HIDDEN, WIDTH);
        ggml_tensor * x = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, WIDTH);
        ggml_tensor * gate = ggml_mul_mat(ctx, wg, x);
        ggml_tensor * up = ggml_mul_mat(ctx, wu, x);
        ggml_tensor * gated = ggml_swiglu_split(ctx, gate, up);
        ggml_tensor * down = ggml_mul_mat(ctx, wd, gated);
        ggml_cgraph * gated_graph = ggml_new_graph_custom(ctx, 32, false);
        ggml_build_forward_expand(gated_graph, gated);
        ggml_cgraph * full_graph = ggml_new_graph_custom(ctx, 32, false);
        ggml_build_forward_expand(full_graph, down);
        ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
        if (!buffer) fail("could not allocate ggml Metal tensors");

        auto gate_weights = capture(argv[2], layer, "gate", ggml_nbytes(wg));
        auto up_weights = capture(argv[2], layer, "up", ggml_nbytes(wu));
        auto down_weights = capture(argv[2], layer, "down", ggml_nbytes(wd));
        auto input_bytes = capture(argv[2], layer, "input", WIDTH * sizeof(float));
        auto captured_gated = capture(argv[2], layer, "gated", HIDDEN * sizeof(float));
        auto captured_output = capture(argv[2], layer, "output", WIDTH * sizeof(float));
        std::vector<float> input(WIDTH);
        std::memcpy(input.data(), input_bytes.data(), input_bytes.size());
        ggml_backend_tensor_set(wg, gate_weights.data(), 0, gate_weights.size());
        ggml_backend_tensor_set(wu, up_weights.data(), 0, up_weights.size());
        ggml_backend_tensor_set(wd, down_weights.data(), 0, down_weights.size());
        ggml_backend_tensor_set(x, input.data(), 0, input.size() * sizeof(float));
        if (ggml_backend_graph_compute(backend, full_graph) != GGML_STATUS_SUCCESS)
            fail("ggml Metal capture comparison failed");
        check_capture(gated, captured_gated);
        check_capture(down, captured_output);

        id<MTLDevice> metal = MTLCreateSystemDefaultDevice();
        if (!metal) fail("Metal GPU unavailable");
        NSError * error = nil;
        id<MTLLibrary> library = [metal newLibraryWithSource:
            [NSString stringWithUTF8String:kernel_source] options:nil error:&error];
        if (!library) {
            std::fprintf(stderr, "Metal compile failed: %s\n", error.localizedDescription.UTF8String);
            return 1;
        }
        id<MTLComputePipelineState> fused_pipeline = [metal newComputePipelineStateWithFunction:
            [library newFunctionWithName:@"q40_gate_up_swiglu"] error:&error];
        id<MTLComputePipelineState> down_pipeline = [metal newComputePipelineStateWithFunction:
            [library newFunctionWithName:@"q40_down"] error:&error];
        if (!fused_pipeline || !down_pipeline ||
            fused_pipeline.threadExecutionWidth != 32 ||
            down_pipeline.threadExecutionWidth != 32 ||
            fused_pipeline.maxTotalThreadsPerThreadgroup < NSUInteger(group_size) ||
            down_pipeline.maxTotalThreadsPerThreadgroup < NSUInteger(group_size))
            fail("Metal pipeline does not admit SIMD32 and requested group size");
        id<MTLCommandQueue> queue = [metal newCommandQueue];
        id<MTLBuffer> mg = [metal newBufferWithBytes:gate_weights.data() length:gate_weights.size()
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> mu = [metal newBufferWithBytes:up_weights.data() length:up_weights.size()
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> md = [metal newBufferWithBytes:down_weights.data() length:down_weights.size()
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> mx = [metal newBufferWithBytes:input.data() length:input.size() * sizeof(float)
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> my = [metal newBufferWithLength:HIDDEN * sizeof(float)
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> mz = [metal newBufferWithLength:WIDTH * sizeof(float)
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> my_separate = [metal newBufferWithLength:HIDDEN * sizeof(float)
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> mz_separate = [metal newBufferWithLength:WIDTH * sizeof(float)
            options:MTLResourceStorageModeShared];
        if (!queue || !mg || !mu || !md || !mx || !my || !mz ||
            !my_separate || !mz_separate)
            fail("Metal buffer allocation failed");

        double setup_ms = elapsed_ms(setup_start);
        auto run_native = [&](bool full) -> Sample {
            auto start = std::chrono::steady_clock::now();
            id<MTLCommandBuffer> command = [queue commandBuffer];
            if (!command) fail("native command buffer allocation failed");
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            if (!encoder) fail("native encoder allocation failed");
            [encoder setComputePipelineState:fused_pipeline];
            [encoder setBuffer:mg offset:0 atIndex:0];
            [encoder setBuffer:mu offset:0 atIndex:1];
            [encoder setBuffer:mx offset:0 atIndex:2];
            [encoder setBuffer:my offset:0 atIndex:3];
            [encoder dispatchThreads:MTLSizeMake(HIDDEN * 8, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(group_size, 1, 1)];
            if (full) {
                [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
                [encoder setComputePipelineState:down_pipeline];
                [encoder setBuffer:md offset:0 atIndex:0];
                [encoder setBuffer:my offset:0 atIndex:1];
                [encoder setBuffer:mz offset:0 atIndex:2];
                [encoder dispatchThreads:MTLSizeMake(WIDTH * 8, 1, 1)
                    threadsPerThreadgroup:MTLSizeMake(group_size, 1, 1)];
            }
            [encoder endEncoding];
            [command commit];
            [command waitUntilCompleted];
            if (command.status != MTLCommandBufferStatusCompleted)
                fail("native Metal compute failed");
            return {elapsed_ms(start),
                    (command.GPUEndTime - command.GPUStartTime) * 1000.0};
        };
        auto run_native_separate = [&](bool wait_between) -> Sample {
            auto start = std::chrono::steady_clock::now();
            double gpu_ms = 0.0;
            id<MTLCommandBuffer> first_command = nil;
            for (bool down_stage : {false, true}) {
                id<MTLCommandBuffer> command = [queue commandBuffer];
                if (!command) fail("separate command buffer allocation failed");
                id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
                if (!encoder) fail("separate encoder allocation failed");
                if (!down_stage) {
                    [encoder setComputePipelineState:fused_pipeline];
                    [encoder setBuffer:mg offset:0 atIndex:0];
                    [encoder setBuffer:mu offset:0 atIndex:1];
                    [encoder setBuffer:mx offset:0 atIndex:2];
                    [encoder setBuffer:my_separate offset:0 atIndex:3];
                    [encoder dispatchThreads:MTLSizeMake(HIDDEN * 8, 1, 1)
                        threadsPerThreadgroup:MTLSizeMake(group_size, 1, 1)];
                } else {
                    [encoder setComputePipelineState:down_pipeline];
                    [encoder setBuffer:md offset:0 atIndex:0];
                    [encoder setBuffer:my_separate offset:0 atIndex:1];
                    [encoder setBuffer:mz_separate offset:0 atIndex:2];
                    [encoder dispatchThreads:MTLSizeMake(WIDTH * 8, 1, 1)
                        threadsPerThreadgroup:MTLSizeMake(group_size, 1, 1)];
                }
                [encoder endEncoding];
                [command commit];
                if (!down_stage && !wait_between) {
                    first_command = command;
                } else {
                    [command waitUntilCompleted];
                    if (command.status != MTLCommandBufferStatusCompleted)
                        fail("separate Metal command failed");
                    gpu_ms += (command.GPUEndTime - command.GPUStartTime) * 1000.0;
                }
            }
            if (first_command) {
                if (first_command.status != MTLCommandBufferStatusCompleted)
                    fail("first queued Metal command failed");
                gpu_ms += (first_command.GPUEndTime - first_command.GPUStartTime) * 1000.0;
            }
            return {elapsed_ms(start), gpu_ms};
        };
        auto run_ggml = [&](bool full) -> double {
            auto start = std::chrono::steady_clock::now();
            if (ggml_backend_graph_compute(backend, full ? full_graph : gated_graph)
                != GGML_STATUS_SUCCESS) fail("ggml Metal compute failed");
            return elapsed_ms(start);
        };
        for (int i = 0; i < 12; ++i) {
            run_ggml(true);
            run_native(true);
        }
        float intermediate_error = check_output(gated, my, HIDDEN, "gated");
        float final_error = check_output(down, mz, WIDTH, "down");
        std::printf("case layer=%d gpu=%s threadgroup=%d setup_ms=%.4f gate_bytes=%zu up_bytes=%zu down_bytes=%zu gated_max_abs_diff=%g down_max_abs_diff=%g\n",
            layer, metal.name.UTF8String, group_size, setup_ms, gate_weights.size(),
            up_weights.size(), down_weights.size(), intermediate_error, final_error);
        for (int repeat = 0; repeat < 20; ++repeat) {
            run_native(true);
            check_output(gated, my, HIDDEN, "reused gated");
            check_output(down, mz, WIDTH, "reused down");
        }
        for (bool full : {false, true}) {
            std::vector<double> ggml_times, native_times, native_gpu_times, differences;
            for (int pair = 0; pair < PAIRS; ++pair) {
                double ggml_total = 0, native_total = 0, native_gpu_total = 0;
                for (int i = 0; i < ITERATIONS; ++i) {
                    if (pair % 2 == 0) {
                        ggml_total += run_ggml(full);
                        Sample n = run_native(full);
                        native_total += n.wall_ms;
                        native_gpu_total += n.gpu_ms;
                    } else {
                        Sample n = run_native(full);
                        native_total += n.wall_ms;
                        native_gpu_total += n.gpu_ms;
                        ggml_total += run_ggml(full);
                    }
                }
                double gm = ggml_total / ITERATIONS, nm = native_total / ITERATIONS;
                ggml_times.push_back(gm);
                native_times.push_back(nm);
                native_gpu_times.push_back(native_gpu_total / ITERATIONS);
                differences.push_back(gm - nm);
                check_output(gated, my, HIDDEN, "post-pair gated");
                if (full) check_output(down, mz, WIDTH, "post-pair down");
                std::printf("pair layer=%d stage=%s index=%d ggml_ms=%.6f native_ms=%.6f native_gpu_ms=%.6f difference_ms=%.6f\n",
                    layer, full ? "full" : "gated", pair, gm, nm,
                    native_gpu_times.back(), differences.back());
            }
            std::printf("summary layer=%d stage=%s ggml_median_ms=%.6f native_median_ms=%.6f native_gpu_median_ms=%.6f paired_difference_median_ms=%.6f\n",
                layer, full ? "full" : "gated", median(ggml_times),
                median(native_times), median(native_gpu_times), median(differences));
        }
        for (bool wait_between : {true, false}) {
          for (int warm = 0; warm < 12; ++warm) {
              run_native(true);
              run_native_separate(wait_between);
          }
          std::vector<double> combined_times, separate_times, combined_gpu_times,
              separate_gpu_times, boundary_differences;
          for (int pair = 0; pair < PAIRS; ++pair) {
            double combined_wall = 0, separate_wall = 0;
            double combined_gpu = 0, separate_gpu = 0;
            for (int i = 0; i < ITERATIONS; ++i) {
                if (pair % 2 == 0) {
                    Sample c = run_native(true), s = run_native_separate(wait_between);
                    combined_wall += c.wall_ms; combined_gpu += c.gpu_ms;
                    separate_wall += s.wall_ms; separate_gpu += s.gpu_ms;
                } else {
                    Sample s = run_native_separate(wait_between), c = run_native(true);
                    separate_wall += s.wall_ms; separate_gpu += s.gpu_ms;
                    combined_wall += c.wall_ms; combined_gpu += c.gpu_ms;
                }
            }
            double cm = combined_wall / ITERATIONS, sm = separate_wall / ITERATIONS;
            combined_times.push_back(cm); separate_times.push_back(sm);
            combined_gpu_times.push_back(combined_gpu / ITERATIONS);
            separate_gpu_times.push_back(separate_gpu / ITERATIONS);
            boundary_differences.push_back(sm - cm);
            check_output(gated, my, HIDDEN, "post-boundary combined gated");
            check_output(down, mz, WIDTH, "post-boundary combined down");
            check_output(gated, my_separate, HIDDEN, "post-boundary separate gated");
            check_output(down, mz_separate, WIDTH, "post-boundary separate down");
            std::printf("boundary_pair layer=%d mode=%s index=%d combined_ms=%.6f separate_ms=%.6f combined_gpu_ms=%.6f separate_gpu_ms=%.6f extra_wall_ms=%.6f\n",
                        layer, wait_between ? "wait" : "queued", pair, cm, sm, combined_gpu_times.back(),
                        separate_gpu_times.back(), boundary_differences.back());
          }
          std::printf("boundary_summary layer=%d mode=%s combined_median_ms=%.6f separate_median_ms=%.6f combined_gpu_median_ms=%.6f separate_gpu_median_ms=%.6f paired_extra_wall_median_ms=%.6f\n",
                      layer, wait_between ? "wait" : "queued", median(combined_times), median(separate_times),
                      median(combined_gpu_times), median(separate_gpu_times),
                      median(boundary_differences));
        }
        ggml_backend_buffer_free(buffer);
        ggml_free(ctx);
        ggml_backend_free(backend);
    }
    return 0;
}
