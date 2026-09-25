// Isolated Qwen3.5-2B FFN decode probe; no runtime backend integration.
// The Q4_0 packed-dot method follows ggml-metal's mul_vec_q_n_f32_impl.
// clang++ -O3 -std=c++17 -fobjc-arc -framework Foundation -framework Metal \
//   -I"$GGML_SOURCE/ggml/include" -L"$GGML_BUNDLE" -Wl,-rpath,"$GGML_BUNDLE" \
//   -lggml -lggml-base scripts/bench-metal-q4-ffn.mm -o /tmp/bench-metal-q4-ffn
// /tmp/bench-metal-q4-ffn "$GGML_BUNDLE/libggml-metal.so"

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

static std::vector<uint8_t> make_weights(size_t bytes, unsigned seed) {
    std::vector<uint8_t> data(bytes);
    if (bytes % 18 != 0) fail("unexpected Q4_0 tensor size");
    for (size_t block = 0; block < bytes / 18; ++block) {
        size_t at = block * 18;
        data[at] = 0;
        data[at + 1] = 0x24; // F16 scale = 1/64.
        for (unsigned i = 0; i < 16; ++i) {
            unsigned low = (block * 17 + i * 7 + seed * 13) & 15;
            unsigned high = (block * 11 + i * 3 + seed * 19) & 15;
            data[at + 2 + i] = static_cast<uint8_t>(low | (high << 4));
        }
    }
    return data;
}

static double elapsed_ms(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count();
}

static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

static float check_output(ggml_backend_t backend, ggml_tensor * tensor,
                          id<MTLBuffer> actual_buffer, int count, const char * label) {
    std::vector<float> expected(count);
    ggml_backend_tensor_get(tensor, expected.data(), 0, count * sizeof(float));
    const float * actual = static_cast<const float *>(actual_buffer.contents);
    float max_abs = 0;
    for (int i = 0; i < count; ++i) {
        float diff = std::fabs(expected[i] - actual[i]);
        max_abs = std::max(max_abs, diff);
        if (!std::isfinite(actual[i]) || diff > 0.005f + 0.0005f * std::fabs(expected[i])) {
            std::fprintf(stderr, "%s mismatch at %d: ggml=%g native=%g diff=%g\n",
                         label, i, expected[i], actual[i], diff);
            std::exit(1);
        }
    }
    return max_abs;
}

int main(int argc, char ** argv) {
    if (argc < 2 || argc > 3)
        fail("usage: bench-metal-q4-ffn LIBGGML_METAL_SO [THREADGROUP_SIZE]");
    int group_size = argc == 3 ? std::atoi(argv[2]) : 128;
    if (group_size != 64 && group_size != 128 && group_size != 256)
        fail("THREADGROUP_SIZE must be 64, 128, or 256");
    @autoreleasepool {
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

        auto gate_weights = make_weights(ggml_nbytes(wg), 1);
        auto up_weights = make_weights(ggml_nbytes(wu), 2);
        auto down_weights = make_weights(ggml_nbytes(wd), 3);
        std::vector<float> input(WIDTH);
        for (int i = 0; i < WIDTH; ++i) input[i] = std::sin(i * 0.013f);
        ggml_backend_tensor_set(wg, gate_weights.data(), 0, gate_weights.size());
        ggml_backend_tensor_set(wu, up_weights.data(), 0, up_weights.size());
        ggml_backend_tensor_set(wd, down_weights.data(), 0, down_weights.size());
        ggml_backend_tensor_set(x, input.data(), 0, input.size() * sizeof(float));

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
        if (!fused_pipeline || !down_pipeline) fail("Metal pipeline creation failed");
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
        if (!queue || !mg || !mu || !md || !mx || !my || !mz)
            fail("Metal buffer allocation failed");

        auto run_native = [&](bool full) -> double {
            auto start = std::chrono::steady_clock::now();
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
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
            return elapsed_ms(start);
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
        float intermediate_error = check_output(backend, gated, my, HIDDEN, "gated");
        float final_error = check_output(backend, down, mz, WIDTH, "down");
        std::printf("gpu=%s threadgroup=%d gated_max_abs_diff=%g down_max_abs_diff=%g\n",
            metal.name.UTF8String, group_size, intermediate_error, final_error);
        for (bool full : {false, true}) {
            std::vector<double> ggml_times, native_times;
            for (int pair = 0; pair < PAIRS; ++pair) {
                double ggml_total = 0, native_total = 0;
                for (int i = 0; i < ITERATIONS; ++i) {
                    if (pair % 2 == 0) {
                        ggml_total += run_ggml(full);
                        native_total += run_native(full);
                    } else {
                        native_total += run_native(full);
                        ggml_total += run_ggml(full);
                    }
                }
                double gm = ggml_total / ITERATIONS, nm = native_total / ITERATIONS;
                ggml_times.push_back(gm);
                native_times.push_back(nm);
                std::printf("stage=%s pair=%d ggml_ms=%.4f native_ms=%.4f\n",
                    full ? "full" : "gated", pair, gm, nm);
            }
            std::printf("stage=%s median_ggml_ms=%.4f median_native_ms=%.4f\n",
                full ? "full" : "gated", median(ggml_times), median(native_times));
        }
        ggml_backend_buffer_free(buffer);
        ggml_free(ctx);
        ggml_backend_free(backend);
    }
    return 0;
}
