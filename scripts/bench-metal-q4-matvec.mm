// Standalone Q4_0 decode matvec probe. This is not a runtime backend.
// Build with the exact pinned ggml source and its Metal bundle:
// clang++ -O3 -std=c++17 -fobjc-arc -framework Foundation -framework Metal \
//   -I"$GGML_SOURCE/ggml/include" -L"$GGML_BUNDLE" -Wl,-rpath,"$GGML_BUNDLE" \
//   -lggml -lggml-base scripts/bench-metal-q4-matvec.mm -o /tmp/bench-metal-q4-matvec
// Run: /tmp/bench-metal-q4-matvec "$GGML_BUNDLE/libggml-metal.so" [WIDTH ROWS]

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

static constexpr int BLOCK = 32;
static constexpr int ITERATIONS = 20;
static constexpr int PAIRS = 5;

static const char * kernel_source = R"METAL(
#include <metal_stdlib>
using namespace metal;

struct Q40Block {
    half scale;
    uchar packed[16];
};

kernel void q40_matvec(
    device const Q40Block * weights [[buffer(0)]],
    device const float * input [[buffer(1)]],
    device float * output [[buffer(2)]],
    constant uint & width [[buffer(3)]],
    constant uint & rows [[buffer(4)]],
    uint tid [[thread_position_in_grid]]) {
    uint row = tid / 32;
    if (row >= rows) return;
    uint lane = tid % 32;
    uint block_lane = lane / 2;
    uint half_lane = lane % 2;
    float value = 0.0f;
    uint blocks_per_row = width / 32;
    for (uint block = block_lane; block < blocks_per_row; block += 16) {
        Q40Block quant = weights[row * blocks_per_row + block];
        float scale = float(quant.scale);
        for (uint i = 0; i < 8; ++i) {
            uchar packed = quant.packed[half_lane * 8 + i];
            uint at = block * 32 + half_lane * 8 + i;
            value = fma(scale * float(int(packed & 15) - 8), input[at], value);
            value = fma(scale * float(int(packed >> 4) - 8), input[at + 16], value);
        }
    }
    float total = simd_sum(value);
    if (lane == 0) output[row] = total;
}
)METAL";

static void fail(const char * reason) {
    std::fprintf(stderr, "%s\n", reason);
    std::exit(1);
}

static double elapsed_ms(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count();
}

static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

int main(int argc, char ** argv) {
    if (argc != 2 && argc != 4)
        fail("usage: bench-metal-q4-matvec LIBGGML_METAL_SO [WIDTH ROWS]");
    const int width = argc == 4 ? std::atoi(argv[2]) : 2048;
    const int rows = argc == 4 ? std::atoi(argv[3]) : 6144;
    if (width < BLOCK || width > 8192 || width % BLOCK != 0 ||
        rows < 4 || rows > 8192 || rows % 4 != 0)
        fail("WIDTH must be a multiple of 32 and ROWS a multiple of 4, both at most 8192");
    @autoreleasepool {
        ggml_backend_reg_t reg = ggml_backend_load(argv[1]);
        if (!reg) fail("could not load pinned ggml Metal plugin");
        ggml_backend_dev_t dev = ggml_backend_reg_dev_get(reg, 0);
        ggml_backend_t backend = ggml_backend_dev_init(dev, nullptr);
        if (!backend) fail("could not initialize ggml Metal device");

        ggml_init_params params = {
            ggml_tensor_overhead() * 16 + ggml_graph_overhead_custom(16, false),
            nullptr, true
        };
        ggml_context * ctx = ggml_init(params);
        if (!ctx) fail("could not initialize ggml context");
        ggml_tensor * w = ggml_new_tensor_2d(ctx, GGML_TYPE_Q4_0, width, rows);
        ggml_tensor * x = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, width);
        ggml_tensor * y = ggml_mul_mat(ctx, w, x);
        ggml_cgraph * graph = ggml_new_graph_custom(ctx, 16, false);
        ggml_build_forward_expand(graph, y);
        ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
        if (!buffer) fail("could not allocate ggml Metal tensors");

        std::vector<uint8_t> weights(ggml_nbytes(w));
        std::vector<float> input(width);
        for (int i = 0; i < width; ++i) input[i] = std::sin(i * 0.013f);
        for (size_t block = 0; block < weights.size() / 18; ++block) {
            size_t at = block * 18;
            weights[at] = 0;
            weights[at + 1] = 0x2c; // F16 scale = 1/16.
            for (int i = 0; i < 16; ++i) {
                uint8_t low = static_cast<uint8_t>((block * 17 + i * 7) & 15);
                uint8_t high = static_cast<uint8_t>((block * 11 + i * 3) & 15);
                weights[at + 2 + i] = static_cast<uint8_t>(low | (high << 4));
            }
        }
        ggml_backend_tensor_set(w, weights.data(), 0, weights.size());
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
        id<MTLFunction> function = [library newFunctionWithName:@"q40_matvec"];
        id<MTLComputePipelineState> pipeline =
            [metal newComputePipelineStateWithFunction:function error:&error];
        if (!pipeline) fail("Metal pipeline creation failed");
        id<MTLCommandQueue> queue = [metal newCommandQueue];
        id<MTLBuffer> mw = [metal newBufferWithBytes:weights.data()
            length:weights.size() options:MTLResourceStorageModeShared];
        id<MTLBuffer> mx = [metal newBufferWithBytes:input.data()
            length:input.size() * sizeof(float) options:MTLResourceStorageModeShared];
        id<MTLBuffer> my = [metal newBufferWithLength:rows * sizeof(float)
            options:MTLResourceStorageModeShared];
        if (!queue || !mw || !mx || !my) fail("Metal buffer allocation failed");

        auto run_native = [&]() -> double {
            auto start = std::chrono::steady_clock::now();
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
            uint32_t gpu_width = width, gpu_rows = rows;
            [encoder setComputePipelineState:pipeline];
            [encoder setBuffer:mw offset:0 atIndex:0];
            [encoder setBuffer:mx offset:0 atIndex:1];
            [encoder setBuffer:my offset:0 atIndex:2];
            [encoder setBytes:&gpu_width length:sizeof(gpu_width) atIndex:3];
            [encoder setBytes:&gpu_rows length:sizeof(gpu_rows) atIndex:4];
            [encoder dispatchThreads:MTLSizeMake(rows * 32, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
            [encoder endEncoding];
            [command commit];
            [command waitUntilCompleted];
            if (command.status != MTLCommandBufferStatusCompleted) fail("native Metal compute failed");
            return elapsed_ms(start);
        };
        auto run_ggml = [&]() -> double {
            auto start = std::chrono::steady_clock::now();
            if (ggml_backend_graph_compute(backend, graph) != GGML_STATUS_SUCCESS)
                fail("ggml Metal compute failed");
            return elapsed_ms(start);
        };
        for (int i = 0; i < 12; ++i) {
            run_ggml();
            run_native();
        }
        std::vector<float> reference(rows);
        ggml_backend_tensor_get(y, reference.data(), 0, rows * sizeof(float));
        const float * actual = static_cast<const float *>(my.contents);
        float worst_abs = 0, worst_scaled = 0;
        for (int i = 0; i < rows; ++i) {
            float diff = std::fabs(reference[i] - actual[i]);
            worst_abs = std::max(worst_abs, diff);
            worst_scaled = std::max(worst_scaled, diff / (0.001f + std::fabs(reference[i])));
            if (!std::isfinite(actual[i]) || diff > 0.001f + 0.0001f * std::fabs(reference[i]))
                fail("native Metal output differs from ggml Metal");
        }
        std::printf("gpu=%s shape=[%d,%d] weight_bytes=%zu max_abs_diff=%.7g max_scaled_diff=%.7g\n",
            metal.name.UTF8String, width, rows, weights.size(), worst_abs, worst_scaled);
        std::vector<double> ggml_times, native_times;
        for (int pair = 0; pair < PAIRS; ++pair) {
            double ggml_total = 0, native_total = 0;
            for (int i = 0; i < ITERATIONS; ++i) {
                if (pair % 2 == 0) {
                    ggml_total += run_ggml();
                    native_total += run_native();
                } else {
                    native_total += run_native();
                    ggml_total += run_ggml();
                }
            }
            double gm = ggml_total / ITERATIONS;
            double nm = native_total / ITERATIONS;
            ggml_times.push_back(gm);
            native_times.push_back(nm);
            std::printf("pair=%d ggml_ms=%.4f native_ms=%.4f\n", pair, gm, nm);
        }
        std::printf("median_ggml_ms=%.4f median_native_ms=%.4f\n",
            median(ggml_times), median(native_times));
        ggml_backend_buffer_free(buffer);
        ggml_free(ctx);
        ggml_backend_free(backend);
    }
    return 0;
}
