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
#include <fstream>
#include <sstream>
#include <sys/stat.h>
#include <limits.h>
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

static std::vector<uint8_t> pack_split(const std::vector<uint8_t> &raw) {
    if (raw.size() % 18) fail("invalid pack length");
    const size_t blocks = raw.size() / 18;
    std::vector<uint8_t> split(raw.size());
    for (size_t b = 0; b < blocks; ++b) {
        std::memcpy(split.data() + 16 * b, raw.data() + 18 * b + 2, 16);
        std::memcpy(split.data() + 16 * blocks + 2 * b, raw.data() + 18 * b, 2);
    }
    return split;
}

static bool reconstructed(const std::vector<uint8_t> &raw,
        const std::vector<uint8_t> &split) {
    if (raw.size() != split.size() || raw.size() % 18) return false;
    const size_t blocks = raw.size() / 18;
    for (size_t b = 0; b < blocks; ++b)
        if (std::memcmp(raw.data() + 18 * b + 2, split.data() + 16 * b, 16)
            || std::memcmp(raw.data() + 18 * b, split.data() + 16 * blocks + 2 * b, 2))
            return false;
    return true;
}

// Bind the measured process to the exact files hashed by the runner, including
// SONAME aliases. Never accept an ambient loader replacement as the control.
static void check_loaded(const char *expected, const char *stem) {
    struct stat wanted{};
    char expected_path[PATH_MAX];
    if (!expected || !realpath(expected, expected_path) || stat(expected, &wanted))
        fail("expected library identity missing");
    const std::string canonical_name = std::string(expected_path).substr(
        std::string(expected_path).find_last_of('/') + 1);
    const std::string version_prefix = std::string(stem) + ".";
    std::ifstream maps("/proc/self/maps");
    std::string line;
    bool found = false;
    while (std::getline(maps, line)) {
        std::istringstream fields(line);
        std::string address, permissions, offset, device, inode, path;
        fields >> address >> permissions >> offset >> device >> inode;
        std::getline(fields, path);
        const size_t first = path.find_first_not_of(' ');
        if (first == std::string::npos) continue;
        path.erase(0, first);
        const std::string name = path.substr(path.find_last_of('/') + 1);
        // CMake's SONAME symlinks normally map a versioned canonical target.
        // Also inspect other versions, so a wrong loaded file still refuses.
        if (name != canonical_name && name != stem && name.rfind(version_prefix, 0) != 0)
            continue;
        struct stat actual{};
        char actual_path[PATH_MAX];
        if (!realpath(path.c_str(), actual_path) || std::strcmp(actual_path, expected_path)
                || stat(path.c_str(), &actual) || actual.st_dev != wanted.st_dev
                || actual.st_ino != wanted.st_ino
                || std::stoull(inode) != uint64_t(wanted.st_ino))
            fail("loaded library path/device/inode mismatch");
        found = true;
    }
    if (!found) fail("expected library is not mapped");
    std::printf("loaded_library=%s device=%llu inode=%llu\n", expected,
        (unsigned long long)wanted.st_dev, (unsigned long long)wanted.st_ino);
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

#if defined(ALIGN_CUDA_Q4_TESTING)
static void failure_owner(int layout, const void *gate, const void *up,
        const void *down, const float *input, const std::vector<float> &reference_gated,
        const std::vector<float> &reference_down) {
    std::vector<float> gated(HIDDEN, 123.0f), output(WIDTH, 123.0f);
    auto fresh = [&]() {
        void *ctx = align_native_cuda_q40_ffn_open_layout(WIDTH, HIDDEN, layout);
        if (!ctx) fail("recovery context allocation failed");
        std::fill(gated.begin(), gated.end(), 123.0f);
        std::fill(output.begin(), output.end(), 123.0f);
        if (align_native_cuda_q40_ffn_read(ctx, gated.data(), HIDDEN, output.data(), WIDTH))
            fail("read succeeded before completed execution");
        if (!std::all_of(gated.begin(), gated.end(), [](float v) { return v == 123.0f; })
            || !std::all_of(output.begin(), output.end(), [](float v) { return v == 123.0f; }))
            fail("premature read modified caller output");
        for (int dependency = 0; dependency < 4; ++dependency)
            if (align_native_cuda_q40_ffn_run(ctx, dependency == 0 ? nullptr : gate,
                    dependency == 1 ? nullptr : up, dependency == 2 ? nullptr : down,
                    dependency == 3 ? nullptr : input)) fail("null dependency admitted");
        if (!align_native_cuda_q40_ffn_run(ctx, gate, up, down, input)
            || !align_native_cuda_q40_ffn_read(ctx, gated.data(), HIDDEN, output.data(), WIDTH))
            fail("fresh-context recovery failed");
        compare(reference_gated, gated, "recovery gated");
        compare(reference_down, output, "recovery down");
        if (align_native_cuda_q40_ffn_read(ctx, gated.data(), HIDDEN - 1, output.data(), WIDTH)
            || align_native_cuda_q40_ffn_read(ctx, gated.data(), HIDDEN, output.data(), WIDTH - 1))
            fail("read admitted wrong counts");
        if (align_native_cuda_q40_ffn_read(ctx, nullptr, HIDDEN, output.data(), WIDTH)
            || align_native_cuda_q40_ffn_read(ctx, gated.data(), HIDDEN, nullptr, WIDTH))
            fail("read admitted null output");
        // All four captured dependencies must remain bound, with recoverable
        // admission refusal and no stale read. No changed address is dereferenced.
        for (int dependency = 0; dependency < 4; ++dependency) {
            const void *g = dependency == 0 ? static_cast<const uint8_t *>(gate) + 16 : gate;
            const void *u = dependency == 1 ? static_cast<const uint8_t *>(up) + 16 : up;
            const void *d = dependency == 2 ? static_cast<const uint8_t *>(down) + 16 : down;
            const float *x = dependency == 3 ? input + 1 : input;
            if (align_native_cuda_q40_ffn_run(ctx, g, u, d, x)
                || align_native_cuda_q40_ffn_read(ctx, gated.data(), HIDDEN, output.data(), WIDTH))
                fail("changed dependency admitted or exposed stale output");
            if (!align_native_cuda_q40_ffn_run(ctx, gate, up, down, input))
                fail("valid replay after admission refusal failed");
        }
        align_native_cuda_q40_ffn_close(ctx);
    };
    fresh();
    for (int operation = 1; operation <= 12; ++operation) {
        if (operation <= 5) {
            align_native_cuda_q40_ffn_test_fail(operation);
            if (align_native_cuda_q40_ffn_open_layout(WIDTH, HIDDEN, layout))
                fail("forced acquisition failure succeeded");
        } else {
            // Submission/completion failures cover both first launch and replay.
            const int attempts = operation == 9 || operation == 10 ? 2 : 1;
            for (int attempt = 0; attempt < attempts; ++attempt) {
                void *ctx = align_native_cuda_q40_ffn_open_layout(WIDTH, HIDDEN, layout);
                if (!ctx) fail("fault context allocation failed");
                if ((operation >= 11 || attempt == 1)
                    && !align_native_cuda_q40_ffn_run(ctx, gate, up, down, input))
                    fail("fault preparation failed");
                align_native_cuda_q40_ffn_test_fail(operation);
                const int accepted = operation >= 11
                    ? align_native_cuda_q40_ffn_read(ctx, gated.data(), HIDDEN, output.data(), WIDTH)
                    : align_native_cuda_q40_ffn_run(ctx, gate, up, down, input);
                if (accepted
                    || align_native_cuda_q40_ffn_run(ctx, gate, up, down, input)
                    || align_native_cuda_q40_ffn_read(ctx, gated.data(), HIDDEN, output.data(), WIDTH))
                    fail("failed context accepted execution or output");
                align_native_cuda_q40_ffn_close(ctx);
            }
        }
        fresh();
    }
    if (align_native_cuda_q40_ffn_run(nullptr, gate, up, down, input)
        || align_native_cuda_q40_ffn_read(nullptr, gated.data(), HIDDEN, output.data(), WIDTH))
        fail("null context admitted");
    align_native_cuda_q40_ffn_close(nullptr);
    std::printf("failure_owner=PASS operations=12 first_and_replay_launch_completion=1 recovery=1 changed_dependencies=4\n");
}
#endif

int main(int argc, char **argv) {
    if (argc != 2 && argc != 3)
        fail("usage: bench-native-cuda-q4-ffn LIBGGML_CUDA_SO [CAPTURE_DIR]");
    const char *capture = argc == 3 ? argv[2] : nullptr;
    const char *layout_mode = std::getenv("ALIGN_CUDA_Q4_LAYOUT");
    if (layout_mode && std::strcmp(layout_mode, "raw") && std::strcmp(layout_mode, "split"))
        fail("ALIGN_CUDA_Q4_LAYOUT must be raw or split");
    const bool split = layout_mode && std::strcmp(layout_mode, "split") == 0;
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
    } else {
        gate_weights = make_weights(WEIGHT_BYTES, 1);
        up_weights = make_weights(WEIGHT_BYTES, 2);
        down_weights = make_weights(WEIGHT_BYTES, 3);
        for (int i = 0; i < WIDTH; ++i) input[i] = std::sin(i * 0.013f);
    }
    // Include every half-scale bit pattern, independent of device admission.
    std::vector<uint8_t> packing_probe(18 * 65536);
    for (size_t b = 0; b < 65536; ++b) {
        packing_probe[18 * b] = uint8_t(b);
        packing_probe[18 * b + 1] = uint8_t(b >> 8);
        for (int j = 0; j < 16; ++j) packing_probe[18 * b + 2 + j] = uint8_t(b + j);
    }
    auto packed_probe = pack_split(packing_probe);
    if (!reconstructed(packing_probe, packed_probe)) fail("packing self-check failed");
    packed_probe[0] ^= 1;
    if (reconstructed(packing_probe, packed_probe)) fail("corrupt payload admitted");
    packed_probe[0] ^= 1;
    packed_probe[16 * 65536] ^= 1;
    if (reconstructed(packing_probe, packed_probe)) fail("corrupt scale admitted");
    std::vector<uint8_t>().swap(packing_probe);
    std::vector<uint8_t>().swap(packed_probe);
    const char *library_dir = std::getenv("ALIGN_CUDA_Q4_LIBRARY_DIR");
    if (!library_dir) fail("run through the identity-binding screen runner");
    check_loaded((std::string(library_dir) + "/libggml.so.0").c_str(), "libggml.so");
    check_loaded((std::string(library_dir) + "/libggml-base.so.0").c_str(), "libggml-base.so");
    ggml_backend_reg_t registry = ggml_backend_load(argv[1]);
    const std::string plugin_path(argv[1]);
    check_loaded(argv[1], plugin_path.substr(plugin_path.find_last_of('/') + 1).c_str());
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
    double packing_ms = 0, candidate_upload_ms = 0, baseline_upload_ms = 0, verification_ms = 0;
    auto upload = [&](void *destination, const std::vector<uint8_t> &raw, bool use_split,
            double &upload_ms) {
        auto start = std::chrono::steady_clock::now();
        std::vector<uint8_t> packed;
        if (use_split) {
            packed = pack_split(raw);
            if (!reconstructed(raw, packed)) fail("weight inverse-byte mismatch");
            packing_ms += elapsed_ms(start);
        }
        const auto &bytes = use_split ? packed : raw;
        if (reinterpret_cast<uintptr_t>(destination) % 16
            || (16 * (bytes.size() / 18)) % 16) fail("weight payload/scale alignment failed");
        start = std::chrono::steady_clock::now();
        if (cudaMemcpy(destination, bytes.data(), bytes.size(), cudaMemcpyHostToDevice)
                != cudaSuccess) fail("weight upload failed");
        upload_ms += elapsed_ms(start);
        start = std::chrono::steady_clock::now();
        std::vector<uint8_t> readback(bytes.size());
        if (cudaMemcpy(readback.data(), destination, readback.size(), cudaMemcpyDeviceToHost)
                != cudaSuccess || readback != bytes) fail("uploaded weight byte mismatch");
        verification_ms += elapsed_ms(start);
    };
    upload(dg, gate_weights, split, candidate_upload_ms);
    upload(du, up_weights, split, candidate_upload_ms);
    upload(dd, down_weights, split, candidate_upload_ms);
    if (cudaMemcpy(dx, input.data(), input.size() * sizeof(float), cudaMemcpyHostToDevice)
            != cudaSuccess) fail("native CUDA input upload failed");
    void *native = align_native_cuda_q40_ffn_open_layout(WIDTH, HIDDEN, split);
    if (native == nullptr) fail("native CUDA FFN init failed");
    if (align_native_cuda_q40_ffn_open(WIDTH - 1, HIDDEN) != nullptr
        || align_native_cuda_q40_ffn_open_layout(WIDTH, HIDDEN - 1, split) != nullptr
        || align_native_cuda_q40_ffn_open_layout(WIDTH, HIDDEN, -1) != nullptr
        || align_native_cuda_q40_ffn_open_layout(WIDTH, HIDDEN, 2) != nullptr
        || align_native_cuda_q40_ffn_run(native, nullptr, du, dd, dx)
        || align_native_cuda_q40_ffn_read(native, nullptr, HIDDEN,
            nullptr, WIDTH)) fail("native CUDA admission accepted invalid input");

#if defined(ALIGN_CUDA_Q4_BASELINE)
    void *bg = nullptr, *bu = nullptr, *bd = nullptr;
    if (cudaMalloc(&bg, WEIGHT_BYTES) != cudaSuccess
        || cudaMalloc(&bu, WEIGHT_BYTES) != cudaSuccess
        || cudaMalloc(&bd, WEIGHT_BYTES) != cudaSuccess)
        fail("disjoint baseline weight allocation failed");
    upload(bg, gate_weights, false, baseline_upload_ms);
    upload(bu, up_weights, false, baseline_upload_ms);
    upload(bd, down_weights, false, baseline_upload_ms);
    if (bg == dg || bu == du || bd == dd) fail("native arms share weight allocations");
    void *baseline = baseline_open(WIDTH, HIDDEN);
    if (baseline == nullptr) fail("baseline CUDA FFN init failed");
    auto run_baseline = [&]() -> double {
        apply_pressure();
        const auto start = std::chrono::steady_clock::now();
        if (!baseline_run(baseline, bg, bu, bd, dx)) fail("baseline CUDA FFN compute failed");
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
        std::printf("baseline_native_bit_identical_gated=%d down=%d\n",
            std::memcmp(baseline_gated.data(), native_gated.data(), HIDDEN * sizeof(float)) == 0,
            std::memcmp(baseline_down.data(), native_down.data(), WIDTH * sizeof(float)) == 0);
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
    const double first_ggml_ms = run_ggml();
#if defined(ALIGN_CUDA_Q4_BASELINE)
    const double first_baseline_ms = run_baseline();
    std::printf("first_baseline_capture_launch_wait_ms=%.6f\n", first_baseline_ms);
#endif
    const double first_native_ms = run_native();
    check_both();
#if defined(ALIGN_CUDA_Q4_TESTING)
    failure_owner(split, dg, du, dd, dx, native_gated, native_down);
#endif
    std::printf("layout=%s capture=%s packing_and_inverse_ms=%.6f candidate_weights_upload_ms=%.6f baseline_weights_upload_ms=%.6f upload_verification_ms=%.6f first_native_capture_launch_wait_ms=%.6f first_ggml_ms=%.6f\n",
        split ? "split" : "raw", capture ? "actual" : "synthetic", packing_ms,
        candidate_upload_ms, baseline_upload_ms, verification_ms,
        first_native_ms, first_ggml_ms);
    std::printf("candidate_weight_bytes=%zu paired_extra_device_bytes=%zu helper_scratch_bytes=41984 max_extra_host_staging_bytes=%zu timed_allocations=0\n",
        3 * WEIGHT_BYTES,
#if defined(ALIGN_CUDA_Q4_BASELINE)
        3 * WEIGHT_BYTES,
#else
        size_t(0),
#endif
        2 * WEIGHT_BYTES);
#if defined(ALIGN_CUDA_Q4_TESTING)
    std::printf("test_build=1 diagnostic_no_speed_verdict=1\n");
#else
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
    if (align_native_cuda_q40_ffn_read(native, native_gated.data(), HIDDEN,
            native_down.data(), WIDTH)) fail("read accepted stale output after refusal");
    run_native();
    std::printf("gated_max_abs_diff=%g down_max_abs_diff=%g\n",
        errors.first, errors.second);

#if defined(ALIGN_CUDA_Q4_BASELINE)
    auto run_control = run_baseline;
#else
    auto run_control = run_ggml;
#endif
    std::vector<double> control_times, native_times, gains;
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
        gains.push_back(control_times.back() - native_times.back());
        std::printf("pair=%d %s_ms=%.6f native_ms=%.6f\n",
            pair, control_label, control_times.back(), native_times.back());
    }
    std::printf("median_%s_ms=%.6f median_native_ms=%.6f\n",
        control_label, median(control_times), median(native_times));
    std::printf("median_paired_gain_ms=%.6f candidate_pair_wins=%zu/%d\n",
        median(gains), size_t(std::count_if(gains.begin(), gains.end(),
            [](double gain) { return gain > 0; })), PAIRS);
#endif
#if defined(ALIGN_CUDA_Q4_BASELINE)
    baseline_close(baseline);
    if (cudaFree(bg) != cudaSuccess || cudaFree(bu) != cudaSuccess
        || cudaFree(bd) != cudaSuccess) fail("baseline weight release failed");
#endif
    align_native_cuda_q40_ffn_close(native);
    if (cudaFree(dx) != cudaSuccess || cudaFree(dd) != cudaSuccess
        || cudaFree(du) != cudaSuccess || cudaFree(dg) != cudaSuccess)
        fail("native input release failed");
    ggml_backend_buffer_free(ggml_buffer);
    ggml_free(ctx);
    ggml_backend_free(backend);
    if (pressure_buffer != nullptr && cudaFree(pressure_buffer) != cudaSuccess)
        fail("cache pressure release failed");
    if (pressure_stream != nullptr && cudaStreamDestroy(pressure_stream) != cudaSuccess)
        fail("cache pressure stream release failed");
    return 0;
}
