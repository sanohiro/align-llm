// Independent Q4_0 decode FFN tile-consumer screen on captured real inputs.
// clang++ -O3 -std=c++17 -fobjc-arc -framework Foundation -framework Metal \
//   -I GGML_INCLUDE -L GGML_BUNDLE -Wl,-rpath,GGML_BUNDLE \
//   scripts/bench-metal-q4-tile-ffn.mm -lggml -lggml-base -o BENCH
// BENCH GGML_BUNDLE/libggml-metal.so CAPTURE_DIR LAYER

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include "ggml.h"
#include "ggml-backend.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

static void require(bool condition, const char *message) {
    if (!condition) { std::fprintf(stderr, "%s\n", message); std::exit(1); }
}

static std::vector<uint8_t> capture(const char *root, int layer, const char *role, size_t bytes) {
    char path[4096];
    require(std::snprintf(path, sizeof(path), "%s/%02d-%s.bin", root, layer, role)
            < int(sizeof(path)), "capture path too long");
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    require(bool(file) && file.tellg() == std::streamoff(bytes), "capture size mismatch");
    std::vector<uint8_t> result(bytes);
    file.seekg(0);
    file.read(reinterpret_cast<char *>(result.data()), bytes);
    require(bool(file), "capture read failed");
    return result;
}

static std::vector<uint8_t> synthetic_q40(size_t bytes, unsigned seed) {
    require(bytes % 18 == 0, "Q4_0 byte count mismatch");
    std::vector<uint8_t> result(bytes);
    for (size_t block = 0; block < bytes / 18; ++block) {
        size_t at = block * 18;
        result[at] = 0;
        result[at + 1] = 0x20; // F16 scale = 1/128.
        for (unsigned i = 0; i < 16; ++i) {
            unsigned low = (block * 17 + i * 7 + seed * 13) & 15;
            unsigned high = (block * 11 + i * 3 + seed * 19) & 15;
            result[at + 2 + i] = uint8_t(low | (high << 4));
        }
    }
    return result;
}

static constexpr const char *shader = R"metal(
#include <metal_stdlib>
using namespace metal;
struct Q40Block { half scale; uchar packed[16]; };
struct Shape { uint width; uint hidden; uint tiles; };
inline float q40_dot(device const Q40Block *weight, float sum_x,
                     thread float *scaled_x, uint half_lane) {
    device const ushort *packed = (device const ushort *)weight->packed + half_lane * 4;
    float value = 0.0f;
    for (uint i = 0; i < 4; ++i) {
        ushort q = packed[i];
        value += scaled_x[i * 2] * float(q & 0x000f);
        value += scaled_x[i * 2 + 1] * float(q & 0x0f00);
        value += scaled_x[i * 2 + 8] * float(q & 0x00f0);
        value += scaled_x[i * 2 + 9] * float(q & 0xf000);
    }
    return float(weight->scale) * (value - 8.0f * sum_x);
}
kernel void tile_ffn(device const Q40Block *gate [[buffer(0)]],
                     device const Q40Block *up [[buffer(1)]],
                     device const Q40Block *down [[buffer(2)]],
                     device const float *input [[buffer(3)]],
                     device float *partials [[buffer(4)]],
                     constant Shape &shape [[buffer(5)]],
                     uint tile_id [[threadgroup_position_in_grid]],
                     uint thread_id [[thread_index_in_threadgroup]]) {
    threadgroup float gated[64];
    uint warp = thread_id / 32, lane = thread_id % 32;
    uint block_lane = lane / 2, half_lane = lane % 2;
    uint first = tile_id * 64;
    uint gate_blocks = shape.width / 32;
    for (uint local_row = warp; local_row < 64; local_row += 16) {
        uint hidden_row = first + local_row;
        float gate_sum = 0.0f, up_sum = 0.0f;
        if (hidden_row < shape.hidden) {
            for (uint block = block_lane; block < gate_blocks; block += 16) {
                device const Q40Block *gb = gate + hidden_row * gate_blocks + block;
                device const Q40Block *ub = up + hidden_row * gate_blocks + block;
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
                gate_sum += q40_dot(gb, sum_x, scaled_x, half_lane);
                up_sum += q40_dot(ub, sum_x, scaled_x, half_lane);
            }
        }
        gate_sum = simd_sum(gate_sum);
        up_sum = simd_sum(up_sum);
        if (lane == 0) gated[local_row] = hidden_row < shape.hidden
            ? (gate_sum / (1.0f + exp(-gate_sum))) * up_sum : 0.0f;
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint down_blocks = shape.hidden / 32;
    for (uint output = warp; output < shape.width; output += 16) {
        device const Q40Block *b0 = down + output * down_blocks + tile_id * 2;
        uint packed0 = uint(b0->packed[lane & 15]);
        uint q0 = lane < 16 ? packed0 & 15 : packed0 >> 4;
        float sum = float(int(q0) - 8) * gated[lane] * float(b0->scale);
        if (first + 32 < shape.hidden) {
            device const Q40Block *b1 = b0 + 1;
            uint packed1 = uint(b1->packed[lane & 15]);
            uint q1 = lane < 16 ? packed1 & 15 : packed1 >> 4;
            sum += float(int(q1) - 8) * gated[lane + 32] * float(b1->scale);
        }
        sum = simd_sum(sum);
        if (lane == 0) partials[tile_id * shape.width + output] = sum;
    }
}
kernel void reduce_tiles(device const float *partials [[buffer(0)]],
                         device float *output [[buffer(1)]],
                         constant Shape &shape [[buffer(2)]],
                         uint id [[thread_position_in_grid]]) {
    if (id >= shape.width) return;
    float value = 0.0f;
    for (uint tile = 0; tile < shape.tiles; ++tile) {
        value += partials[tile * shape.width + id];
    }
    output[id] = value;
}
)metal";

struct Shape { uint32_t width, hidden, tiles; };

static double ms(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count();
}

static double compare(const float *expected, const float *actual, size_t count,
                      const char *label) {
    double maximum = 0;
    for (size_t i = 0; i < count; ++i) {
        double difference = std::abs(double(expected[i]) - actual[i]);
        maximum = std::max(maximum, difference);
        if (!std::isfinite(expected[i]) || !std::isfinite(actual[i])
            || difference > 0.005 + 0.0005 * std::abs(expected[i])) {
            std::fprintf(stderr, "%s mismatch at %zu: expected=%g actual=%g diff=%g\n",
                         label, i, expected[i], actual[i], difference);
            std::exit(1);
        }
    }
    return maximum;
}

static void screen(const char *plugin, const char *root, int layer,
                   id<MTLDevice> metal, id<MTLComputePipelineState> tile_pipeline,
                   id<MTLComputePipelineState> reduce_pipeline,
                   uint32_t width, uint32_t hidden, bool synthetic, bool timed) {
    require(width > 0 && width <= 2048 && hidden > 0 && hidden <= 6144
            && width % 32 == 0 && hidden % 32 == 0, "unsupported local shape");
    Shape shape{width, hidden, (hidden + 63) / 64};
    size_t partial_bytes = size_t(shape.tiles) * width * sizeof(float);
    require(partial_bytes <= 1024 * 1024, "partial scratch exceeds screen ceiling");
    auto setup = std::chrono::steady_clock::now();
    ggml_backend_reg_t registry = ggml_backend_load(plugin);
    require(registry != nullptr, "ggml Metal plugin load failed");
    ggml_backend_t backend = ggml_backend_dev_init(ggml_backend_reg_dev_get(registry, 0), nullptr);
    require(backend != nullptr, "ggml Metal backend unavailable");
    ggml_context *context = ggml_init({ggml_tensor_overhead() * 16
        + ggml_graph_overhead_custom(16, false), nullptr, true});
    require(context != nullptr, "ggml context allocation failed");
    ggml_tensor *wg = ggml_new_tensor_2d(context, GGML_TYPE_Q4_0, width, hidden);
    ggml_tensor *wu = ggml_new_tensor_2d(context, GGML_TYPE_Q4_0, width, hidden);
    ggml_tensor *wd = ggml_new_tensor_2d(context, GGML_TYPE_Q4_0, hidden, width);
    ggml_tensor *x = ggml_new_tensor_1d(context, GGML_TYPE_F32, width);
    ggml_tensor *g = ggml_mul_mat(context, wg, x);
    ggml_tensor *u = ggml_mul_mat(context, wu, x);
    ggml_tensor *gated = ggml_swiglu_split(context, g, u);
    ggml_tensor *out = ggml_mul_mat(context, wd, gated);
    ggml_cgraph *graph = ggml_new_graph_custom(context, 16, false);
    ggml_build_forward_expand(graph, out);
    ggml_backend_buffer_t reference_buffer = ggml_backend_alloc_ctx_tensors(context, backend);
    require(reference_buffer != nullptr, "ggml reference allocation failed");
    auto gate_bytes = synthetic ? synthetic_q40(ggml_nbytes(wg), 1)
                                : capture(root, layer, "gate", ggml_nbytes(wg));
    auto up_bytes = synthetic ? synthetic_q40(ggml_nbytes(wu), 2)
                              : capture(root, layer, "up", ggml_nbytes(wu));
    auto down_bytes = synthetic ? synthetic_q40(ggml_nbytes(wd), 3)
                                : capture(root, layer, "down", ggml_nbytes(wd));
    std::vector<float> input(width);
    if (synthetic) {
        for (uint32_t i = 0; i < width; ++i) input[i] = std::sin(i * 0.013f);
    } else {
        auto raw = capture(root, layer, "input", width * sizeof(float));
        std::memcpy(input.data(), raw.data(), raw.size());
    }
    ggml_backend_tensor_set(wg, gate_bytes.data(), 0, gate_bytes.size());
    ggml_backend_tensor_set(wu, up_bytes.data(), 0, up_bytes.size());
    ggml_backend_tensor_set(wd, down_bytes.data(), 0, down_bytes.size());
    ggml_backend_tensor_set(x, input.data(), 0, input.size() * sizeof(float));
    id<MTLBuffer> gate_buffer = [metal newBufferWithBytes:gate_bytes.data()
        length:gate_bytes.size() options:MTLResourceStorageModeShared];
    id<MTLBuffer> up_buffer = [metal newBufferWithBytes:up_bytes.data()
        length:up_bytes.size() options:MTLResourceStorageModeShared];
    id<MTLBuffer> down_buffer = [metal newBufferWithBytes:down_bytes.data()
        length:down_bytes.size() options:MTLResourceStorageModeShared];
    id<MTLBuffer> input_buffer = [metal newBufferWithBytes:input.data()
        length:input.size() * sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> partial_buffer = [metal newBufferWithLength:partial_bytes
        options:MTLResourceStorageModeShared];
    id<MTLBuffer> output_buffer = [metal newBufferWithLength:width * sizeof(float)
        options:MTLResourceStorageModeShared];
    id<MTLCommandQueue> queue = [metal newCommandQueue];
    require(gate_buffer && up_buffer && down_buffer && input_buffer && partial_buffer
            && output_buffer && queue, "native Metal allocation failed");
    double setup_ms = ms(setup);
    auto reference = [&]() {
        auto start = std::chrono::steady_clock::now();
        require(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS,
                "ggml reference compute failed");
        return ms(start);
    };
    auto native = [&](double *gpu) {
        auto start = std::chrono::steady_clock::now();
        id<MTLCommandBuffer> command = [queue commandBuffer];
        require(command != nil, "native command allocation failed");
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        require(encoder != nil, "native encoder allocation failed");
        [encoder setComputePipelineState:tile_pipeline];
        [encoder setBuffer:gate_buffer offset:0 atIndex:0];
        [encoder setBuffer:up_buffer offset:0 atIndex:1];
        [encoder setBuffer:down_buffer offset:0 atIndex:2];
        [encoder setBuffer:input_buffer offset:0 atIndex:3];
        [encoder setBuffer:partial_buffer offset:0 atIndex:4];
        [encoder setBytes:&shape length:sizeof(shape) atIndex:5];
        [encoder dispatchThreadgroups:MTLSizeMake(shape.tiles, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(512, 1, 1)];
        [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
        [encoder setComputePipelineState:reduce_pipeline];
        [encoder setBuffer:partial_buffer offset:0 atIndex:0];
        [encoder setBuffer:output_buffer offset:0 atIndex:1];
        [encoder setBytes:&shape length:sizeof(shape) atIndex:2];
        [encoder dispatchThreads:MTLSizeMake(width, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        [encoder endEncoding];
        [command commit];
        [command waitUntilCompleted];
        require(command.status == MTLCommandBufferStatusCompleted,
                "native command failed");
        if (gpu != nullptr) {
            *gpu = command.GPUEndTime > command.GPUStartTime
                ? (command.GPUEndTime - command.GPUStartTime) * 1000.0 : 0.0;
        }
        return ms(start);
    };
    reference();
    native(nullptr);
    std::vector<float> reference_output(width);
    ggml_backend_tensor_get(out, reference_output.data(), 0, width * sizeof(float));
    double max_diff = compare(reference_output.data(),
        static_cast<const float *>(output_buffer.contents), width, "native FFN");
    std::vector<float> captured;
    if (!synthetic) {
        auto raw = capture(root, layer, "output", width * sizeof(float));
        captured.resize(width);
        std::memcpy(captured.data(), raw.data(), raw.size());
        double captured_diff = compare(captured.data(), reference_output.data(), width,
                                       "ggml captured FFN");
        std::printf("capture_diff=%g ", captured_diff);
    }
    std::printf("shape=%u/%u layer=%d max_abs=%g scratch=%zu setup_ms=%.3f\n",
                width, hidden, layer, max_diff, partial_bytes, setup_ms);
    auto check_reused_output = [&]() {
        std::vector<float> current(width);
        ggml_backend_tensor_get(out, current.data(), 0, width * sizeof(float));
        compare(current.data(), static_cast<const float *>(output_buffer.contents),
                width, "reused native FFN");
        if (!captured.empty()) {
            compare(captured.data(), current.data(), width, "reused captured FFN");
        }
    };
    // Keep readback out of timed operations while checking every reuse in this
    // separate sequence and the final output of each measured pair.
    for (int i = 0; i < 20; ++i) {
        reference();
        native(nullptr);
        check_reused_output();
    }
    std::printf("reuse_checks=20\n");
    if (timed) {
        for (int i = 0; i < 12; ++i) { reference(); native(nullptr); }
        for (int pair = 0; pair < 5; ++pair) {
            double elapsed[2]{0, 0}, gpu_total = 0;
            for (int i = 0; i < 20; ++i) {
                for (int order = 0; order < 2; ++order) {
                    int arm = (pair + i + order) % 2;
                    if (arm == 0) elapsed[0] += reference();
                    else {
                        double gpu = 0;
                        elapsed[1] += native(&gpu);
                        gpu_total += gpu;
                    }
                }
            }
            std::printf("pair=%d ggml_ms=%.6f native_ms=%.6f native_gpu_ms=%.6f\n",
                        pair, elapsed[0] / 20, elapsed[1] / 20, gpu_total / 20);
            check_reused_output();
        }
        std::printf("pair_output_checks=5\n");
    }
    ggml_backend_buffer_free(reference_buffer);
    ggml_free(context);
    ggml_backend_free(backend);
}

int main(int argc, char **argv) {
    require(argc == 4, "usage: bench-metal-q4-tile-ffn METAL_PLUGIN CAPTURE_DIR LAYER");
    int layer = std::atoi(argv[3]);
    require(layer == 3 || layer == 23, "first screen admits captured Q4_0 down layers 3 or 23");
    @autoreleasepool {
        id<MTLDevice> metal = MTLCreateSystemDefaultDevice();
        require(metal != nil, "Metal device unavailable");
        auto start = std::chrono::steady_clock::now();
        NSError *error = nil;
        id<MTLLibrary> library = [metal newLibraryWithSource:
            [NSString stringWithUTF8String:shader] options:nil error:&error];
        if (library == nil) {
            std::fprintf(stderr, "Metal compile failed: %s\n",
                         error.localizedDescription.UTF8String);
            return 1;
        }
        id<MTLFunction> first = [library newFunctionWithName:@"tile_ffn"];
        id<MTLFunction> second = [library newFunctionWithName:@"reduce_tiles"];
        require(first && second, "Metal shader functions unavailable");
        id<MTLComputePipelineState> tile_pipeline =
            [metal newComputePipelineStateWithFunction:first error:&error];
        id<MTLComputePipelineState> reduce_pipeline =
            [metal newComputePipelineStateWithFunction:second error:&error];
        require(tile_pipeline && reduce_pipeline
                && tile_pipeline.threadExecutionWidth == 32
                && tile_pipeline.maxTotalThreadsPerThreadgroup >= 512
                && reduce_pipeline.maxTotalThreadsPerThreadgroup >= 256,
                "Metal pipeline cannot admit 512 threads / SIMD32");
        std::printf("pipeline_compile_ms=%.3f\n", ms(start));
        screen(argv[1], argv[2], layer, metal, tile_pipeline, reduce_pipeline,
               2048, 6144, false, true);
        screen(argv[1], argv[2], layer, metal, tile_pipeline, reduce_pipeline,
               256, 96, true, false);
    }
}
