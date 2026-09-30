// Independent CUDA Q4_0 FFN screen against the pinned ggml CUDA graph.
#include "native_cuda_q40_ffn.h"

#if defined(ALIGN_CUDA_Q4_BASELINE)
extern "C" void *baseline_open(int, int);
extern "C" int baseline_run(void *, const void *, const void *, const void *, const float *);
extern "C" int baseline_read(void *, float *, size_t, float *, size_t);
extern "C" void baseline_close(void *);
#endif

#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"

#include <cuda_runtime.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

static constexpr int WIDTH = 2048;
static constexpr int HIDDEN = 6144;
static constexpr int WARMUPS = 12;
static constexpr int PAIRS = 5;
static constexpr int ITERATIONS = 20;
static constexpr size_t WEIGHT_BYTES = 7077888;
static constexpr size_t PRESSURE_BYTES = 128 * 1024 * 1024;

__global__ static void pressure_store(uint4 *storage, size_t count) {
    for (size_t i = blockIdx.x * blockDim.x + threadIdx.x; i < count;
            i += size_t(gridDim.x) * blockDim.x)
        storage[i] = make_uint4(unsigned(i), unsigned(i + 1), unsigned(i + 2), unsigned(i + 3));
}

[[noreturn]] static void fail(const char *message) {
    std::fprintf(stderr, "native CUDA FFN screen: %s\n", message);
    std::exit(1);
}

static std::vector<uint8_t> make_weights(size_t bytes, unsigned seed) {
    if (bytes % 18 != 0) fail("unexpected Q4_0 tensor size");
    std::vector<uint8_t> data(bytes);
    for (size_t block = 0; block < bytes / 18; ++block) {
        const size_t at = block * 18;
        data[at] = 0;
        data[at + 1] = 0x24;  // F16 scale 1/64.
        for (unsigned i = 0; i < 16; ++i) {
            const unsigned low = (block * 17 + i * 7 + seed * 13) & 15;
            const unsigned high = (block * 11 + i * 3 + seed * 19) & 15;
            data[at + 2 + i] = uint8_t(low | (high << 4));
        }
    }
    return data;
}

static std::vector<uint8_t> read_exact(const char *directory, const char *name,
                                       size_t expected) {
    const std::string path = std::string(directory) + "/" + name;
    FILE *file = std::fopen(path.c_str(), "rb");
    if (!file) fail("capture file missing");
    std::vector<uint8_t> bytes(expected);
    const size_t count = std::fread(bytes.data(), 1, expected, file);
    const int trailing = std::fgetc(file);
    const int io_error = std::ferror(file);
    const int close_status = std::fclose(file);
    if (count != expected || trailing != EOF || io_error || close_status != 0)
        fail("capture file size or read mismatch");
    return bytes;
}

static std::vector<float> read_f32(const char *directory, const char *name,
                                   size_t count) {
    auto bytes = read_exact(directory, name, count * sizeof(float));
    std::vector<float> values(count);
    std::memcpy(values.data(), bytes.data(), bytes.size());
    for (float value : values) if (!std::isfinite(value)) fail("nonfinite F32 capture");
    return values;
}

static float compare(const std::vector<float> &expected,
                     const std::vector<float> &actual, const char *label) {
    if (expected.size() != actual.size()) fail("comparison shape mismatch");
    float worst = 0.0f;
    for (size_t i = 0; i < actual.size(); ++i) {
        const float diff = std::fabs(expected[i] - actual[i]);
        if (!std::isfinite(actual[i]) || !std::isfinite(expected[i]) ||
            diff > 0.005f + 0.0005f * std::fabs(expected[i])) {
            std::fprintf(stderr, "%s mismatch at %zu: expected=%g actual=%g diff=%g\n",
                         label, i, expected[i], actual[i], diff);
            std::exit(1);
        }
        worst = std::max(worst, diff);
    }
    return worst;
}

static double elapsed_ms(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - start).count();
}

static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

static float check_row(ggml_tensor *tensor, const std::vector<float> &actual,
        const char *label) {
    std::vector<float> expected(actual.size());
    ggml_backend_tensor_get(tensor, expected.data(), 0, expected.size() * sizeof(float));
    return compare(expected, actual, label);
}

int main(int argc, char **argv) {
    if (argc != 2 && argc != 3)
        fail("usage: bench-native-cuda-q4-ffn LIBGGML_CUDA_SO [CAPTURE_DIR]");
    const char *capture = argc == 3 ? argv[2] : nullptr;
    const char *pressure_mode = std::getenv("ALIGN_CUDA_Q4_CACHE_PRESSURE");
    if (pressure_mode && std::strcmp(pressure_mode, "0") != 0
            && std::strcmp(pressure_mode, "1") != 0)
        fail("ALIGN_CUDA_Q4_CACHE_PRESSURE must be 0 or 1");
    const bool pressure = pressure_mode && std::strcmp(pressure_mode, "1") == 0;
    std::vector<uint8_t> gate_weights, up_weights, down_weights;
    std::vector<float> input(WIDTH), captured_gated, captured_down;
    if (capture) {
        const char expected[] = "q4-ffn-capture-v1 2048 6144 18\n";
        auto geometry = read_exact(capture, "geometry.txt", sizeof(expected) - 1);
        if (geometry.size() != sizeof(expected) - 1 ||
            std::memcmp(geometry.data(), expected, sizeof(expected) - 1) != 0)
            fail("capture schema or geometry mismatch");
        auto complete = read_exact(capture, "complete.txt", 2);
        if (complete[0] != '1' || complete[1] != '\n') fail("capture incomplete");
        gate_weights = read_exact(capture, "gate.bin", WEIGHT_BYTES);
        up_weights = read_exact(capture, "up.bin", WEIGHT_BYTES);
        down_weights = read_exact(capture, "down.bin", WEIGHT_BYTES);
        input = read_f32(capture, "input.bin", WIDTH);
        captured_gated = read_f32(capture, "gated.bin", HIDDEN);
        captured_down = read_f32(capture, "output.bin", WIDTH);
    }
    ggml_backend_reg_t registry = ggml_backend_load(argv[1]);
    if (registry == nullptr || ggml_backend_reg_dev_count(registry) != 1)
        fail("pinned ggml CUDA plugin must have exactly one device");
    ggml_backend_dev_t device = ggml_backend_reg_dev_get(registry, 0);
    if (device == nullptr) fail("pinned ggml CUDA device unavailable");
    ggml_backend_t backend = ggml_backend_dev_init(device, nullptr);
    if (backend == nullptr) fail("pinned ggml CUDA backend init failed");
    cudaDeviceProp properties{};
    if (cudaGetDeviceProperties(&properties, 0) != cudaSuccess)
        fail("CUDA device query failed");
    std::printf("device=%s ggml_device=%s\n", properties.name,
        ggml_backend_dev_description(device));
    uint4 *pressure_buffer = nullptr;
    cudaStream_t pressure_stream = nullptr;
    if (pressure) {
        if (properties.l2CacheSize <= 0 || PRESSURE_BYTES <= 2ULL * properties.l2CacheSize)
            fail("pressure buffer must exceed twice device L2 capacity");
        if (cudaStreamCreateWithFlags(&pressure_stream, cudaStreamNonBlocking) != cudaSuccess
                || cudaMalloc(&pressure_buffer, PRESSURE_BYTES) != cudaSuccess)
            fail("cache pressure allocation failed");
    }
    std::printf("cache_pressure_bytes=%zu device_l2_bytes=%d pressure_excluded_from_timer=1\n",
        pressure ? PRESSURE_BYTES : 0, properties.l2CacheSize);
    auto apply_pressure = [&]() {
        if (!pressure) return;
        pressure_store<<<1024, 256, 0, pressure_stream>>>(
            pressure_buffer, PRESSURE_BYTES / sizeof(uint4));
        const cudaError_t submitted = cudaGetLastError();
        const cudaError_t completed = cudaStreamSynchronize(pressure_stream);
        if (submitted != cudaSuccess || completed != cudaSuccess)
            fail("cache pressure execution failed");
    };

    ggml_init_params params = {
        ggml_tensor_overhead() * 32 + ggml_graph_overhead_custom(32, false),
        nullptr, true
    };
    ggml_context *ctx = ggml_init(params);
    if (ctx == nullptr) fail("ggml context allocation failed");
    ggml_tensor *wg = ggml_new_tensor_2d(ctx, GGML_TYPE_Q4_0, WIDTH, HIDDEN);
    ggml_tensor *wu = ggml_new_tensor_2d(ctx, GGML_TYPE_Q4_0, WIDTH, HIDDEN);
    ggml_tensor *wd = ggml_new_tensor_2d(ctx, GGML_TYPE_Q4_0, HIDDEN, WIDTH);
    ggml_tensor *x = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, WIDTH);
    ggml_tensor *gate = ggml_mul_mat(ctx, wg, x);
    ggml_tensor *up = ggml_mul_mat(ctx, wu, x);
    ggml_tensor *gated = ggml_swiglu_split(ctx, gate, up);
    ggml_tensor *down = ggml_mul_mat(ctx, wd, gated);
    ggml_cgraph *graph = ggml_new_graph_custom(ctx, 32, false);
    ggml_build_forward_expand(graph, down);
    ggml_backend_buffer_t ggml_buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    if (ggml_buffer == nullptr) fail("ggml CUDA tensor allocation failed");

    if (!capture) {
        gate_weights = make_weights(ggml_nbytes(wg), 1);
        up_weights = make_weights(ggml_nbytes(wu), 2);
        down_weights = make_weights(ggml_nbytes(wd), 3);
        for (int i = 0; i < WIDTH; ++i) input[i] = std::sin(i * 0.013f);
    }
    if (ggml_nbytes(wg) != gate_weights.size() ||
        ggml_nbytes(wu) != up_weights.size() ||
        ggml_nbytes(wd) != down_weights.size()) fail("ggml Q4_0 geometry mismatch");
    ggml_backend_tensor_set(wg, gate_weights.data(), 0, gate_weights.size());
    ggml_backend_tensor_set(wu, up_weights.data(), 0, up_weights.size());
    ggml_backend_tensor_set(wd, down_weights.data(), 0, down_weights.size());
    ggml_backend_tensor_set(x, input.data(), 0, input.size() * sizeof(float));

    void *dg = nullptr, *du = nullptr, *dd = nullptr;
    float *dx = nullptr;
    if (cudaMalloc(&dg, gate_weights.size()) != cudaSuccess
        || cudaMalloc(&du, up_weights.size()) != cudaSuccess
        || cudaMalloc(&dd, down_weights.size()) != cudaSuccess
        || cudaMalloc(&dx, input.size() * sizeof(float)) != cudaSuccess)
        fail("native CUDA input allocation failed");
    if (cudaMemcpy(dg, gate_weights.data(), gate_weights.size(), cudaMemcpyHostToDevice)
            != cudaSuccess
        || cudaMemcpy(du, up_weights.data(), up_weights.size(), cudaMemcpyHostToDevice)
            != cudaSuccess
        || cudaMemcpy(dd, down_weights.data(), down_weights.size(), cudaMemcpyHostToDevice)
            != cudaSuccess
        || cudaMemcpy(dx, input.data(), input.size() * sizeof(float), cudaMemcpyHostToDevice)
            != cudaSuccess) fail("native CUDA input upload failed");
    void *native = align_native_cuda_q40_ffn_open(WIDTH, HIDDEN);
    if (native == nullptr) fail("native CUDA FFN init failed");
    if (align_native_cuda_q40_ffn_open(WIDTH - 1, HIDDEN) != nullptr
        || align_native_cuda_q40_ffn_run(native, nullptr, du, dd, dx)
        || align_native_cuda_q40_ffn_read(native, nullptr, HIDDEN,
            nullptr, WIDTH)) fail("native CUDA admission accepted invalid input");

#if defined(ALIGN_CUDA_Q4_BASELINE)
    void *baseline = baseline_open(WIDTH, HIDDEN);
    if (baseline == nullptr) fail("baseline CUDA FFN init failed");
    auto run_baseline = [&]() -> double {
        apply_pressure();
        const auto start = std::chrono::steady_clock::now();
        if (!baseline_run(baseline, dg, du, dd, dx)) fail("baseline CUDA FFN compute failed");
        return elapsed_ms(start);
    };
    const char *control_label = "baseline";
#else
    const char *control_label = "ggml";
#endif
    auto run_ggml = [&]() -> double {
        apply_pressure();
        const auto start = std::chrono::steady_clock::now();
        if (ggml_backend_graph_compute(backend, graph) != GGML_STATUS_SUCCESS)
            fail("ggml CUDA graph compute failed");
        // The synchronous ggml entrypoint already waits for this graph.
        return elapsed_ms(start);
    };
    auto run_native = [&]() -> double {
        apply_pressure();
        const auto start = std::chrono::steady_clock::now();
        if (!align_native_cuda_q40_ffn_run(native, dg, du, dd, dx))
            fail("native CUDA FFN compute failed");
        return elapsed_ms(start);
    };
    std::vector<float> native_gated(HIDDEN), native_down(WIDTH);
    auto check_both = [&]() -> std::pair<float, float> {
        if (!align_native_cuda_q40_ffn_read(native, native_gated.data(), native_gated.size(),
                native_down.data(), native_down.size())) fail("native CUDA output read failed");
        const float gated_error = check_row(gated, native_gated, "gated");
        const float down_error = check_row(down, native_down, "down");
#if defined(ALIGN_CUDA_Q4_BASELINE)
        std::vector<float> baseline_gated(HIDDEN), baseline_down(WIDTH);
        if (!baseline_read(baseline, baseline_gated.data(), baseline_gated.size(),
                baseline_down.data(), baseline_down.size())) fail("baseline CUDA output read failed");
        check_row(gated, baseline_gated, "baseline gated");
        check_row(down, baseline_down, "baseline down");
        compare(baseline_gated, native_gated, "baseline/native gated");
        compare(baseline_down, native_down, "baseline/native down");
        if (capture) {
            compare(captured_gated, baseline_gated, "captured baseline gated");
            compare(captured_down, baseline_down, "captured baseline down");
        }
#endif
        if (capture) {
            std::vector<float> ggml_gated(HIDDEN), ggml_down(WIDTH);
            ggml_backend_tensor_get(gated, ggml_gated.data(), 0, HIDDEN * sizeof(float));
            ggml_backend_tensor_get(down, ggml_down.data(), 0, WIDTH * sizeof(float));
            compare(captured_gated, ggml_gated, "captured ggml gated");
            compare(captured_down, ggml_down, "captured ggml down");
            compare(captured_gated, native_gated, "captured native gated");
            compare(captured_down, native_down, "captured native down");
        }
        return {gated_error, down_error};
    };
    for (int i = 0; i < WARMUPS; ++i) {
        run_ggml();
#if defined(ALIGN_CUDA_Q4_BASELINE)
        run_baseline();
#endif
        run_native();
    }
    auto errors = check_both();
    if (align_native_cuda_q40_ffn_run(native, static_cast<uint8_t *>(dg) + 1,
            du, dd, dx)) fail("captured CUDA graph accepted a changed weight pointer");
    std::printf("gated_max_abs_diff=%g down_max_abs_diff=%g\n",
        errors.first, errors.second);

#if defined(ALIGN_CUDA_Q4_BASELINE)
    auto run_control = run_baseline;
#else
    auto run_control = run_ggml;
#endif
    std::vector<double> control_times, native_times;
    for (int pair = 0; pair < PAIRS; ++pair) {
        double control_ms = 0.0, native_ms = 0.0;
        for (int i = 0; i < ITERATIONS; ++i) {
            if (pair % 2 == 0) {
                control_ms += run_control();
                native_ms += run_native();
            } else {
                native_ms += run_native();
                control_ms += run_control();
            }
        }
        check_both();
        control_times.push_back(control_ms / ITERATIONS);
        native_times.push_back(native_ms / ITERATIONS);
        std::printf("pair=%d %s_ms=%.6f native_ms=%.6f\n",
            pair, control_label, control_times.back(), native_times.back());
    }
    std::printf("median_%s_ms=%.6f median_native_ms=%.6f\n",
        control_label, median(control_times), median(native_times));
#if defined(ALIGN_CUDA_Q4_BASELINE)
    baseline_close(baseline);
#endif
    align_native_cuda_q40_ffn_close(native);
    cudaFree(dx);
    cudaFree(dd);
    cudaFree(du);
    cudaFree(dg);
    ggml_backend_buffer_free(ggml_buffer);
    ggml_free(ctx);
    ggml_backend_free(backend);
    if (pressure_buffer != nullptr && cudaFree(pressure_buffer) != cudaSuccess)
        fail("cache pressure release failed");
    if (pressure_stream != nullptr && cudaStreamDestroy(pressure_stream) != cudaSuccess)
        fail("cache pressure stream release failed");
    return 0;
}
