// Independent Q4_0 down-projection split-K screen using actual captured bytes.
// This is a developer probe, not an inference runtime.
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

static void require(bool ok, const char *message) {
    if (!ok) { std::fprintf(stderr, "%s\n", message); std::exit(1); }
}

static std::vector<uint8_t> captured(const char *root, int layer, const char *role, size_t bytes) {
    char path[4096];
    require(std::snprintf(path, sizeof(path), "%s/%02d-%s.bin", root, layer, role)
            < int(sizeof(path)), "capture path too long");
    std::ifstream in(path, std::ios::binary | std::ios::ate);
    require(bool(in) && in.tellg() == std::streamoff(bytes), "capture size mismatch");
    std::vector<uint8_t> data(bytes);
    in.seekg(0);
    in.read(reinterpret_cast<char *>(data.data()), bytes);
    require(bool(in), "capture read failed");
    return data;
}

static constexpr const char *shader = R"metal(
#include <metal_stdlib>
using namespace metal;
struct Q40Block { half scale; uchar packed[16]; };
struct Shape { uint hidden; uint rows; uint splits; uint blocks_per_split; };
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
kernel void q40_down_split(device const Q40Block *weights [[buffer(0)]],
                           device const float *input [[buffer(1)]],
                           device float *partials [[buffer(2)]],
                           constant Shape &shape [[buffer(3)]],
                           uint tid [[thread_position_in_grid]]) {
    uint simd_id = tid / 32;
    uint row_groups = shape.rows / 4;
    uint split = simd_id / row_groups;
    uint row = (simd_id % row_groups) * 4;
    if (split >= shape.splits || row >= shape.rows) return;
    uint lane = tid % 32;
    uint block_lane = lane / 2;
    uint half_lane = lane % 2;
    uint blocks_per_row = shape.hidden / 32;
    uint first = split * shape.blocks_per_split;
    uint end = min(first + shape.blocks_per_split, blocks_per_row);
    float value[4] = {0.0f};
    for (uint block = first + block_lane; block < end; block += 16) {
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
        for (uint r = 0; r < 4; ++r)
            value[r] += q40_dot(weights + (row + r) * blocks_per_row + block,
                                sum_x, scaled_x, half_lane);
    }
    for (uint r = 0; r < 4; ++r) {
        float total = simd_sum(value[r]);
        if (lane == 0) partials[split * shape.rows + row + r] = total;
    }
}
kernel void reduce_splits(device const float *partials [[buffer(0)]],
                          device float *output [[buffer(1)]],
                          constant Shape &shape [[buffer(2)]],
                          uint row [[thread_position_in_grid]]) {
    if (row >= shape.rows) return;
    float result = 0.0f;
    for (uint split = 0; split < shape.splits; ++split)
        result += partials[split * shape.rows + row];
    output[row] = result;
}
)metal";

struct Shape { uint32_t hidden, rows, splits, blocks_per_split; };
struct Sample { double wall_ms, gpu_ms; };
struct Arm {
    uint32_t splits;
    id<MTLBuffer> weight;
    id<MTLBuffer> input;
    id<MTLBuffer> partial;
    id<MTLBuffer> output;
};

static double ms(std::chrono::steady_clock::time_point since) {
    return std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - since).count();
}
static double median(std::vector<double> data) {
    std::sort(data.begin(), data.end());
    return data[data.size() / 2];
}
static double compare(const float *expected, const float *actual, size_t count,
                      const char *label) {
    double maximum = 0.0;
    for (size_t i = 0; i < count; ++i) {
        double difference = std::abs(double(expected[i]) - double(actual[i]));
        maximum = std::max(maximum, difference);
        if (!std::isfinite(expected[i]) || !std::isfinite(actual[i]) ||
            difference > 0.005 + 0.0005 * std::abs(double(expected[i]))) {
            std::fprintf(stderr, "%s mismatch at %zu: reference=%g actual=%g diff=%g\n",
                         label, i, expected[i], actual[i], difference);
            std::exit(1);
        }
    }
    return maximum;
}
static std::vector<uint8_t> synthetic_weights(size_t bytes) {
    require(bytes % 18 == 0, "synthetic Q4_0 byte count mismatch");
    std::vector<uint8_t> data(bytes);
    for (size_t block = 0; block < bytes / 18; ++block) {
        size_t at = block * 18;
        data[at] = 0;
        data[at + 1] = 0x20; // F16 1/128.
        for (unsigned i = 0; i < 16; ++i)
            data[at + 2 + i] = uint8_t(((block + i * 7) & 15) |
                                        (((block * 3 + i * 11) & 15) << 4));
    }
    return data;
}

static void screen(const char *plugin, const char *root, int layer,
                   id<MTLDevice> metal, id<MTLComputePipelineState> down_pipeline,
                   id<MTLComputePipelineState> reduce_pipeline) {
    const bool synthetic = layer < 0;
    const uint32_t hidden = synthetic ? 160 : 6144;
    const uint32_t rows = synthetic ? 64 : 2048;
    require(hidden % 32 == 0 && rows % 4 == 0, "unsupported screen shape");
    auto setup = std::chrono::steady_clock::now();
    ggml_backend_reg_t registry = ggml_backend_load(plugin);
    require(registry != nullptr, "ggml Metal plugin load failed");
    ggml_backend_t backend = ggml_backend_dev_init(ggml_backend_reg_dev_get(registry, 0), nullptr);
    require(backend != nullptr, "ggml Metal device unavailable");
    ggml_context *context = ggml_init({ggml_tensor_overhead() * 12
        + ggml_graph_overhead_custom(12, false), nullptr, true});
    require(context != nullptr, "ggml context allocation failed");
    ggml_tensor *w = ggml_new_tensor_2d(context, GGML_TYPE_Q4_0, hidden, rows);
    ggml_tensor *x = ggml_new_tensor_1d(context, GGML_TYPE_F32, hidden);
    ggml_tensor *y = ggml_mul_mat(context, w, x);
    ggml_cgraph *graph = ggml_new_graph_custom(context, 12, false);
    ggml_build_forward_expand(graph, y);
    ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(context, backend);
    require(buffer != nullptr, "ggml tensor allocation failed");
    std::vector<uint8_t> weights = synthetic ? synthetic_weights(ggml_nbytes(w))
        : captured(root, layer, "down", ggml_nbytes(w));
    std::vector<float> input(hidden);
    if (synthetic) {
        for (uint32_t i = 0; i < hidden; ++i) input[i] = std::sin(double(i) * 0.031);
    } else {
        auto bytes = captured(root, layer, "gated", size_t(hidden) * sizeof(float));
        std::memcpy(input.data(), bytes.data(), bytes.size());
    }
    ggml_backend_tensor_set(w, weights.data(), 0, weights.size());
    ggml_backend_tensor_set(x, input.data(), 0, size_t(hidden) * sizeof(float));
    require(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS,
            "ggml reference compute failed");
    std::vector<float> reference(rows);
    ggml_backend_tensor_get(y, reference.data(), 0, size_t(rows) * sizeof(float));
    if (!synthetic) {
        auto bytes = captured(root, layer, "output", size_t(rows) * sizeof(float));
        require(std::memcmp(bytes.data(), reference.data(), bytes.size()) == 0,
                "captured and rebuilt ggml outputs differ");
    }
    id<MTLCommandQueue> queue = [metal newCommandQueue];
    require(queue != nil, "Metal command queue allocation failed");
    std::vector<Arm> arms;
    for (uint32_t splits : {1u, 2u, 4u}) {
        Arm arm{};
        arm.splits = splits;
        arm.weight = [metal newBufferWithBytes:weights.data() length:weights.size()
            options:MTLResourceStorageModeShared];
        arm.input = [metal newBufferWithBytes:input.data() length:size_t(hidden) * sizeof(float)
            options:MTLResourceStorageModeShared];
        size_t partial_bytes = size_t(splits) * rows * sizeof(float);
        require(partial_bytes <= 64 * 1024, "partial scratch ceiling exceeded");
        arm.partial = [metal newBufferWithLength:partial_bytes
            options:MTLResourceStorageModeShared];
        arm.output = splits == 1 ? arm.partial : [metal newBufferWithLength:size_t(rows) * sizeof(float)
            options:MTLResourceStorageModeShared];
        require(arm.weight != nil && arm.input != nil && arm.partial != nil && arm.output != nil,
                "Metal buffer allocation failed");
        arms.push_back(arm);
    }
    double setup_ms = ms(setup);
    auto run_ggml = [&]() -> Sample {
        auto begin = std::chrono::steady_clock::now();
        require(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS,
                "ggml Metal compute failed");
        return {ms(begin), 0.0};
    };
    auto run_native = [&](Arm &arm) -> Sample {
        auto begin = std::chrono::steady_clock::now();
        id<MTLCommandBuffer> command = [queue commandBuffer];
        require(command != nil, "Metal command buffer allocation failed");
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        require(encoder != nil, "Metal encoder allocation failed");
        Shape shape{hidden, rows, arm.splits,
            (hidden / 32 + arm.splits - 1) / arm.splits};
        [encoder setComputePipelineState:down_pipeline];
        [encoder setBuffer:arm.weight offset:0 atIndex:0];
        [encoder setBuffer:arm.input offset:0 atIndex:1];
        [encoder setBuffer:arm.partial offset:0 atIndex:2];
        [encoder setBytes:&shape length:sizeof(shape) atIndex:3];
        [encoder dispatchThreads:MTLSizeMake(size_t(rows / 4) * arm.splits * 32, 1, 1)
            threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
        if (arm.splits > 1) {
            [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
            [encoder setComputePipelineState:reduce_pipeline];
            [encoder setBuffer:arm.partial offset:0 atIndex:0];
            [encoder setBuffer:arm.output offset:0 atIndex:1];
            [encoder setBytes:&shape length:sizeof(shape) atIndex:2];
            [encoder dispatchThreads:MTLSizeMake(rows, 1, 1)
                threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
        }
        [encoder endEncoding];
        [command commit];
        [command waitUntilCompleted];
        require(command.status == MTLCommandBufferStatusCompleted, "Metal command failed");
        return {ms(begin), (command.GPUEndTime - command.GPUStartTime) * 1000.0};
    };
    for (int warm = 0; warm < 12; ++warm) {
        run_ggml();
        for (auto &arm : arms) run_native(arm);
    }
    for (auto &arm : arms) {
        double maximum = compare(reference.data(), static_cast<const float *>(arm.output.contents),
                                 rows, "native down");
        std::printf("check layer=%d splits=%u max_abs=%.9g\n", layer, arm.splits, maximum);
        for (int repeat = 0; repeat < 20; ++repeat) {
            run_native(arm);
            compare(reference.data(), static_cast<const float *>(arm.output.contents),
                    rows, "reused native down");
        }
    }
    if (synthetic) {
        std::printf("case layer=tail hidden=%u rows=%u setup_ms=%.4f\n", hidden, rows, setup_ms);
    } else {
        std::printf("case layer=%d hidden=%u rows=%u setup_ms=%.4f weight_bytes=%zu\n",
                    layer, hidden, rows, setup_ms, weights.size());
    }
    if (!synthetic) {
        for (uint32_t candidate : {1u, 2u, 4u}) {
            const size_t candidate_index = candidate == 1 ? 0 : candidate == 2 ? 1 : 2;
            for (int control = 0; control < (candidate == 1 ? 1 : 2); ++control) {
                std::vector<double> control_ms, control_gpu, candidate_ms, candidate_gpu, differences;
                for (int pair = 0; pair < 5; ++pair) {
                    double control_total = 0, control_gpu_total = 0;
                    double candidate_total = 0, gpu_total = 0;
                    for (int repeat = 0; repeat < 20; ++repeat) {
                        auto control_run = [&]() { return control == 0 ? run_ggml()
                            : run_native(arms[0]); };
                        if (pair % 2 == 0) {
                            Sample g = control_run();
                            control_total += g.wall_ms;
                            control_gpu_total += g.gpu_ms;
                            Sample c = run_native(arms[candidate_index]);
                            candidate_total += c.wall_ms;
                            gpu_total += c.gpu_ms;
                        } else {
                            Sample c = run_native(arms[candidate_index]);
                            candidate_total += c.wall_ms;
                            gpu_total += c.gpu_ms;
                            Sample g = control_run();
                            control_total += g.wall_ms;
                            control_gpu_total += g.gpu_ms;
                        }
                    }
                    double c_ms = control_total / 20.0;
                    double n_ms = candidate_total / 20.0;
                    control_ms.push_back(c_ms);
                    control_gpu.push_back(control_gpu_total / 20.0);
                    candidate_ms.push_back(n_ms);
                    candidate_gpu.push_back(gpu_total / 20.0);
                    differences.push_back(c_ms - n_ms);
                    compare(reference.data(), static_cast<const float *>(arms[0].output.contents),
                            rows, "post-pair unsplit down");
                    compare(reference.data(),
                            static_cast<const float *>(arms[candidate_index].output.contents),
                            rows, "post-pair split down");
                    std::printf("pair layer=%d control=%s splits=%u index=%d control_ms=%.6f control_gpu_ms=%.6f split_ms=%.6f split_gpu_ms=%.6f difference_ms=%.6f\n",
                                layer, control == 0 ? "ggml" : "unsplit", candidate, pair,
                                c_ms, control_gpu.back(), n_ms, candidate_gpu.back(), differences.back());
                }
                std::printf("summary layer=%d control=%s splits=%u control_median_ms=%.6f control_gpu_median_ms=%.6f split_median_ms=%.6f split_gpu_median_ms=%.6f paired_difference_median_ms=%.6f\n",
                            layer, control == 0 ? "ggml" : "unsplit", candidate,
                            median(control_ms), median(control_gpu), median(candidate_ms), median(candidate_gpu),
                            median(differences));
            }
        }
    }
    ggml_backend_buffer_free(buffer);
    ggml_free(context);
    ggml_backend_free(backend);
}

int main(int argc, char **argv) {
    require(argc == 3, "usage: bench-metal-q4-down-split LIBGGML_METAL_SO CAPTURE_DIR");
    @autoreleasepool {
        id<MTLDevice> metal = MTLCreateSystemDefaultDevice();
        require(metal != nil && metal.maxThreadsPerThreadgroup.width >= 128,
                "Metal device does not support the required group size");
        NSError *error = nil;
        id<MTLLibrary> library = [metal newLibraryWithSource:
            [NSString stringWithUTF8String:shader] options:nil error:&error];
        if (!library) {
            std::fprintf(stderr, "Metal compile failed: %s\n", error.localizedDescription.UTF8String);
            return 1;
        }
        id<MTLComputePipelineState> down = [metal newComputePipelineStateWithFunction:
            [library newFunctionWithName:@"q40_down_split"] error:&error];
        require(down != nil && down.threadExecutionWidth == 32,
                "Q4_0 down pipeline requires SIMD32");
        id<MTLComputePipelineState> reduce = [metal newComputePipelineStateWithFunction:
            [library newFunctionWithName:@"reduce_splits"] error:&error];
        require(reduce != nil, "split reduction pipeline unavailable");
        std::printf("device name=%s simd=%zu max_group=%zu\n", metal.name.UTF8String,
                    size_t(down.threadExecutionWidth), size_t(down.maxTotalThreadsPerThreadgroup));
        screen(argv[1], argv[2], -1, metal, down, reduce);
        screen(argv[1], argv[2], 3, metal, down, reduce);
        screen(argv[1], argv[2], 23, metal, down, reduce);
    }
    return 0;
}
