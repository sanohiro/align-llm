// Independent actual-weight CUDA Q6_K four-column screen; no product selection.
// Q6_K unpacking and Q8_1 conversion follow pinned ggml's format and CUDA path.
// MIT License
// Copyright (c) 2023-2026 the ggml authors
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
#include "ggml.h"
#include "ggml-backend.h"

#include <cuda_fp16.h>
#include <cuda_runtime.h>

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

static constexpr int WIDTH = 2048, ROWS = 248320, COLUMNS = 4;
static constexpr int WARMUPS = 12, PAIRS = 5, ITERATIONS = 20;
static constexpr size_t WEIGHT_BYTES = size_t(WIDTH / 256) * ROWS * 210;

struct Q6Block { uint8_t ql[128], qh[64]; int8_t scales[16]; __half d; };
static_assert(sizeof(Q6Block) == 210, "Q6_K block layout changed");
struct Q8Block { int8_t q[32]; __half d, sum; };
static_assert(sizeof(Q8Block) == 36, "Q8_1 block layout changed");

[[noreturn]] static void fail(const char *message) {
    std::fprintf(stderr, "native CUDA Q6_K screen: %s\n", message);
    std::exit(1);
}

static void checked(cudaError_t status, const char *message) {
    if (status != cudaSuccess) {
        std::fprintf(stderr, "native CUDA Q6_K screen: %s: %s\n",
                     message, cudaGetErrorString(status));
        std::exit(1);
    }
}

static std::string file(const char *directory, const char *name) {
    return std::string(directory) + "/" + name;
}

static std::vector<uint8_t> bytes(const std::string &path, size_t expected) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream || stream.tellg() != std::streamoff(expected)) fail("capture size differs");
    stream.seekg(0);
    std::vector<uint8_t> result(expected);
    if (!stream.read(reinterpret_cast<char *>(result.data()), expected))
        fail("capture read failed");
    return result;
}

static std::vector<float> floats(const std::string &path, size_t count) {
    auto raw = bytes(path, count * sizeof(float));
    std::vector<float> result(count);
    std::memcpy(result.data(), raw.data(), raw.size());
    for (float x : result) if (!std::isfinite(x)) fail("nonfinite capture value");
    return result;
}

static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

// Match the pinned CUDA graph's per-32-value Q8_1 input conversion.
__global__ static void quantize_input(const float *input, Q8Block *quantized) {
    const int lane = threadIdx.x & 31;
    const int block = (blockIdx.x * blockDim.x + threadIdx.x) / 32;
    const float x = input[block * 32 + lane];
    float maximum = fabsf(x);
    for (int offset = 16; offset > 0; offset >>= 1)
        maximum = fmaxf(maximum, __shfl_down_sync(0xffffffff, maximum, offset));
    maximum = __shfl_sync(0xffffffff, maximum, 0);
    const float d = maximum / 127.0f;
    quantized[block].q[lane] = maximum == 0.0f ? 0 : int8_t(roundf(x / d));
    if (lane == 0) quantized[block].d = __float2half(d);
}

// Adapted from the captured-weight Metal screen's four-column hypothesis.
// Each warp handles one output row and reuses one Q6_K block for four inputs.
__global__ static void q6_batch4(const Q6Block *weights, const Q8Block *input,
                                  float *output) {
    const int lane = threadIdx.x & 31;
    const int row = (blockIdx.x * blockDim.x + threadIdx.x) / 32;
    if (row >= ROWS) return;
    const int tid = lane / 2, ix = lane & 1;
    const int ip = tid / 8, l0 = 4 * (tid % 8), is = 8 * ip + l0 / 16;
    float acc[COLUMNS] = {};
    for (int block = ix; block < WIDTH / 256; block += 2) {
        const Q6Block &q = weights[row * (WIDTH / 256) + block];
        const float scale = __half2float(q.d);
        uint32_t packed[4] = {};
#pragma unroll
        for (int l = 0; l < 4; ++l) {
            const uint8_t q1 = q.ql[64 * ip + l0 + l];
            const uint8_t q2 = q.ql[64 * ip + l0 + 32 + l];
            const uint8_t high = q.qh[32 * ip + l0 + l];
            const int v0 = int((q1 & 15) | ((high & 3) << 4)) - 32;
            const int v1 = int((q2 & 15) | ((high & 12) << 2)) - 32;
            const int v2 = int((q1 >> 4) | (high & 48)) - 32;
            const int v3 = int((q2 >> 4) | ((high & 192) >> 2)) - 32;
            packed[0] |= uint32_t(uint8_t(v0)) << (8 * l);
            packed[1] |= uint32_t(uint8_t(v1)) << (8 * l);
            packed[2] |= uint32_t(uint8_t(v2)) << (8 * l);
            packed[3] |= uint32_t(uint8_t(v3)) << (8 * l);
        }
#pragma unroll
        for (int col = 0; col < COLUMNS; ++col) {
            const int group = col * (WIDTH / 32) + block * 8 + ip * 4;
            const int p0 = __dp4a(int(packed[0]),
                *reinterpret_cast<const int *>(input[group + 0].q + l0), 0);
            const int p1 = __dp4a(int(packed[1]),
                *reinterpret_cast<const int *>(input[group + 1].q + l0), 0);
            const int p2 = __dp4a(int(packed[2]),
                *reinterpret_cast<const int *>(input[group + 2].q + l0), 0);
            const int p3 = __dp4a(int(packed[3]),
                *reinterpret_cast<const int *>(input[group + 3].q + l0), 0);
            float local = 0.0f;
            local += __half2float(input[group + 0].d) * float(p0 * q.scales[is]);
            local += __half2float(input[group + 1].d) * float(p1 * q.scales[is + 2]);
            local += __half2float(input[group + 2].d) * float(p2 * q.scales[is + 4]);
            local += __half2float(input[group + 3].d) * float(p3 * q.scales[is + 6]);
            acc[col] += scale * local;
        }
    }
#pragma unroll
    for (int col = 0; col < COLUMNS; ++col) {
        float value = acc[col];
        for (int offset = 16; offset > 0; offset >>= 1)
            value += __shfl_down_sync(0xffffffff, value, offset);
        if (lane == 0) output[col * ROWS + row] = value;
    }
}

static double elapsed(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count();
}

int main(int argc, char **argv) {
    if (argc != 3) fail("usage: bench-native-cuda-q6-batch4 CUDA_PLUGIN CAPTURE_DIR");
    std::ifstream geometry(file(argv[2], "geometry.txt"));
    std::string marker, trailing;
    int64_t width = 0, rows = 0;
    int type = -1;
    geometry >> marker >> width >> rows >> type;
    if (!geometry || (geometry >> trailing) || marker != "q6-capture-v1" ||
        width != WIDTH || rows != ROWS || type != 14) fail("unexpected capture geometry");
    std::ifstream complete(file(argv[2], "complete.txt"));
    int captured = 0;
    complete >> captured;
    if (!complete || captured != 3 || (complete >> trailing)) fail("incomplete capture");
    auto weight = bytes(file(argv[2], "weights.bin"), WEIGHT_BYTES);
    std::vector<float> captured_input[3], captured_output[3];
    std::vector<float> input(size_t(WIDTH) * COLUMNS);
    for (int col = 0; col < 3; ++col) {
        captured_input[col] = floats(file(argv[2], (std::to_string(col) + "-input.bin").c_str()), WIDTH);
        captured_output[col] = floats(file(argv[2], (std::to_string(col) + "-output.bin").c_str()), ROWS);
    }
    for (int col = 0; col < COLUMNS; ++col)
        std::copy(captured_input[col % 3].begin(), captured_input[col % 3].end(),
                  input.begin() + size_t(col) * WIDTH);

    auto reg = ggml_backend_load(argv[1]);
    if (!reg || ggml_backend_reg_dev_count(reg) != 1) fail("pinned CUDA plugin admission failed");
    auto dev = ggml_backend_reg_dev_get(reg, 0);
    auto backend = ggml_backend_dev_init(dev, nullptr);
    if (!backend) fail("ggml CUDA backend initialization failed");
    cudaDeviceProp properties{};
    checked(cudaGetDeviceProperties(&properties, 0), "device query failed");
    std::printf("device=%s ggml_device=%s weight_bytes=%zu\n", properties.name,
                ggml_backend_dev_description(dev), WEIGHT_BYTES);
    ggml_init_params params = {ggml_tensor_overhead() * 8 +
        ggml_graph_overhead_custom(8, false), nullptr, true};
    auto ctx = ggml_init(params);
    if (!ctx) fail("ggml context allocation failed");
    auto w = ggml_new_tensor_2d(ctx, GGML_TYPE_Q6_K, WIDTH, ROWS);
    auto x = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, WIDTH, COLUMNS);
    auto y = ggml_mul_mat(ctx, w, x);
    auto graph = ggml_new_graph_custom(ctx, 8, false);
    ggml_build_forward_expand(graph, y);
    auto buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    if (!buffer || ggml_nbytes(w) != WEIGHT_BYTES) fail("ggml tensor allocation failed");
    for (size_t at = 0; at < WEIGHT_BYTES; at += 1 << 20)
        ggml_backend_tensor_set(w, weight.data() + at, at,
                                std::min(size_t(1 << 20), WEIGHT_BYTES - at));
    ggml_backend_tensor_set(x, input.data(), 0, input.size() * sizeof(float));

    Q6Block *native_weight = nullptr;
    float *native_input = nullptr, *native_output = nullptr;
    Q8Block *native_quantized = nullptr;
    cudaStream_t stream = nullptr;
    checked(cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking), "stream creation failed");
    checked(cudaMalloc(&native_weight, WEIGHT_BYTES), "native weight allocation failed");
    checked(cudaMalloc(&native_input, input.size() * sizeof(float)), "native input allocation failed");
    checked(cudaMalloc(&native_quantized, size_t(COLUMNS) * (WIDTH / 32) * sizeof(Q8Block)),
            "native Q8 input allocation failed");
    checked(cudaMalloc(&native_output, size_t(ROWS) * COLUMNS * sizeof(float)),
            "native output allocation failed");
    checked(cudaMemcpyAsync(native_weight, weight.data(), WEIGHT_BYTES,
                            cudaMemcpyHostToDevice, stream), "native weight upload failed");
    checked(cudaMemcpyAsync(native_input, input.data(), input.size() * sizeof(float),
                            cudaMemcpyHostToDevice, stream), "native input upload failed");
    checked(cudaStreamSynchronize(stream), "native upload completion failed");
    const auto run_ggml = [&]() {
        auto start = std::chrono::steady_clock::now();
        if (ggml_backend_graph_compute(backend, graph) != GGML_STATUS_SUCCESS)
            fail("ggml graph compute failed");
        return elapsed(start);
    };
    const auto run_native = [&]() {
        auto start = std::chrono::steady_clock::now();
        quantize_input<<<COLUMNS * WIDTH / 256, 256, 0, stream>>>(native_input, native_quantized);
        checked(cudaGetLastError(), "native quantization launch failed");
        q6_batch4<<<(ROWS + 7) / 8, 256, 0, stream>>>(native_weight, native_quantized,
                                                       native_output);
        checked(cudaGetLastError(), "native launch failed");
        checked(cudaStreamSynchronize(stream), "native completion failed");
        return elapsed(start);
    };
    std::vector<float> ggml_output(size_t(ROWS) * COLUMNS), native_result(ggml_output.size());
    const auto check_outputs = [&]() {
        ggml_backend_tensor_get(y, ggml_output.data(), 0, ggml_output.size() * sizeof(float));
        checked(cudaMemcpy(native_result.data(), native_output,
                           native_result.size() * sizeof(float), cudaMemcpyDeviceToHost),
                "native output read failed");
        double worst = 0.0;
        for (int col = 0; col < COLUMNS; ++col) {
            int reference_greedy = 0, ggml_greedy = 0, native_greedy = 0;
            for (int row = 0; row < ROWS; ++row) {
                const auto at = size_t(col) * ROWS + row;
                const float expected = captured_output[col % 3][row];
                const float baseline = ggml_output[at], observed = native_result[at];
                const double diff = std::fabs(double(observed) - expected);
                if (!std::isfinite(baseline) || !std::isfinite(observed) ||
                    std::fabs(double(baseline) - expected) > 0.01 || diff > 0.01) {
                    std::fprintf(stderr, "column=%d row=%d captured=%g ggml=%g native=%g\n",
                                 col, row, expected, baseline, observed);
                    fail("captured-output numeric bound failed");
                }
                worst = std::max(worst, diff);
                if (expected > captured_output[col % 3][reference_greedy]) reference_greedy = row;
                if (baseline > ggml_output[size_t(col) * ROWS + ggml_greedy]) ggml_greedy = row;
                if (observed > native_result[size_t(col) * ROWS + native_greedy]) native_greedy = row;
            }
            if (ggml_greedy != reference_greedy || native_greedy != reference_greedy)
                fail("greedy index differs from captured output");
        }
        return worst;
    };
    run_ggml(); run_native();
    double worst = check_outputs();
    for (int i = 0; i < WARMUPS; ++i) { run_ggml(); run_native(); }
    worst = std::max(worst, check_outputs());
    std::vector<double> ggml_times, native_times, paired;
    for (int pair = 0; pair < PAIRS; ++pair) {
        double a = 0, b = 0;
        for (int i = 0; i < ITERATIONS; ++i) {
            if (pair % 2 == 0) { a += run_ggml(); b += run_native(); }
            else { b += run_native(); a += run_ggml(); }
        }
        worst = std::max(worst, check_outputs());
        a /= ITERATIONS; b /= ITERATIONS;
        ggml_times.push_back(a); native_times.push_back(b); paired.push_back(a-b);
        std::printf("pair=%d ggml_ms=%.6f native_ms=%.6f\n", pair, a, b);
    }
    std::printf("max_abs_diff=%.9g median_ggml_ms=%.6f median_native_ms=%.6f "
                "median_paired_gain_ms=%.6f native_wins=%d/%d\n", worst,
                median(ggml_times), median(native_times), median(paired),
                int(std::count_if(paired.begin(), paired.end(), [](double x) { return x > 0; })), PAIRS);
    checked(cudaFree(native_output), "native output cleanup failed");
    checked(cudaFree(native_quantized), "native Q8 input cleanup failed");
    checked(cudaFree(native_input), "native input cleanup failed");
    checked(cudaFree(native_weight), "native weight cleanup failed");
    checked(cudaStreamDestroy(stream), "stream cleanup failed");
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
    ggml_backend_free(backend);
    return 0;
}
