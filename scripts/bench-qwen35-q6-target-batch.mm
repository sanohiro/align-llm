// Developer-only Q6_K output-head target-batch screen on captured model bytes.
// It does not implement speculative decoding or product inference.
#import <Foundation/Foundation.h>
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
    if (!condition) { std::fprintf(stderr, "Q6_BATCH error=%s\n", message); std::exit(1); }
}

static std::string member(const char *directory, const std::string &name) {
    return std::string(directory) + "/" + name;
}

static std::vector<float> read_f32(const std::string &path, size_t count) {
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    require(file && file.tellg() == std::streamoff(count * sizeof(float)), "input capture size");
    file.seekg(0);
    std::vector<float> result(count);
    file.read(reinterpret_cast<char *>(result.data()), count * sizeof(float));
    require(bool(file), "input capture read");
    for (float value : result) require(std::isfinite(value), "nonfinite input capture");
    return result;
}

static double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

int main(int argc, char **argv) {
    require(argc == 3, "usage: bench-qwen35-q6-target-batch PLUGIN CAPTURE_DIR");
    std::ifstream geometry(member(argv[2], "geometry.txt"));
    std::string marker, trailing;
    int64_t width = 0, rows = 0;
    int type = -1;
    geometry >> marker >> width >> rows >> type;
    require(geometry && !(geometry >> trailing) && marker == "q6-capture-v1"
            && type == 14 && width == 2048 && rows == 248320,
            "this captured 2B Q6_K screen needs the expected geometry");
    const size_t bytes = size_t(width / 256) * size_t(rows) * 210;
    std::ifstream weights(member(argv[2], "weights.bin"), std::ios::binary | std::ios::ate);
    require(weights && weights.tellg() == std::streamoff(bytes), "weight capture size");
    weights.seekg(0);
    std::vector<float> captured[3];
    for (int i = 0; i < 3; ++i)
        captured[i] = read_f32(member(argv[2], std::to_string(i) + "-input.bin"), width);

    auto reg = ggml_backend_load(argv[1]);
    require(reg != nullptr, "pinned Metal plugin load");
    auto backend = ggml_backend_dev_init(ggml_backend_reg_dev_get(reg, 0), nullptr);
    require(backend != nullptr, "Metal backend init");
    ggml_init_params params = {ggml_tensor_overhead() * 128 +
        ggml_graph_overhead_custom(32, false) * 24, nullptr, true};
    auto ctx = ggml_init(params);
    require(ctx != nullptr, "ggml context init");
    auto w = ggml_new_tensor_2d(ctx, GGML_TYPE_Q6_K, width, rows);
    constexpr int MAX_K = 16;
    ggml_tensor *single_x[MAX_K], *single_y[MAX_K];
    ggml_cgraph *single_graph[MAX_K];
    for (int i = 0; i < MAX_K; ++i) {
        single_x[i] = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, width);
        single_y[i] = ggml_mul_mat(ctx, w, single_x[i]);
        single_graph[i] = ggml_new_graph_custom(ctx, 8, false);
        ggml_build_forward_expand(single_graph[i], single_y[i]);
    }
    const int counts[] = {4, 8, 16};
    ggml_tensor *batch_x[3], *batch_y[3];
    ggml_cgraph *batch_graph[3];
    for (int j = 0; j < 3; ++j) {
        batch_x[j] = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, width, counts[j]);
        batch_y[j] = ggml_mul_mat(ctx, w, batch_x[j]);
        batch_graph[j] = ggml_new_graph_custom(ctx, 8, false);
        ggml_build_forward_expand(batch_graph[j], batch_y[j]);
    }
    auto allocation = ggml_backend_alloc_ctx_tensors(ctx, backend);
    require(allocation != nullptr && ggml_nbytes(w) == bytes, "ggml shared allocation");
    std::vector<uint8_t> chunk(1 << 20);
    for (size_t at = 0; at < bytes;) {
        size_t length = std::min(chunk.size(), bytes - at);
        weights.read(reinterpret_cast<char *>(chunk.data()), length);
        require(bool(weights), "weight capture read");
        ggml_backend_tensor_set(w, chunk.data(), at, length);
        at += length;
    }
    for (int i = 0; i < MAX_K; ++i)
        ggml_backend_tensor_set(single_x[i], captured[i % 3].data(), 0, width * sizeof(float));
    for (int j = 0; j < 3; ++j) {
        std::vector<float> inputs(size_t(width) * counts[j]);
        for (int i = 0; i < counts[j]; ++i)
            std::memcpy(inputs.data() + size_t(i) * width, captured[i % 3].data(),
                        width * sizeof(float));
        ggml_backend_tensor_set(batch_x[j], inputs.data(), 0,
                                inputs.size() * sizeof(float));
    }
    std::vector<float> reference[3];
    for (int i = 0; i < 3; ++i) {
        require(ggml_backend_graph_compute(backend, single_graph[i]) == GGML_STATUS_SUCCESS,
                "single projection check compute");
        reference[i].resize(rows);
        ggml_backend_tensor_get(single_y[i], reference[i].data(), 0,
                                size_t(rows) * sizeof(float));
    }
    std::printf("{\"event\":\"setup\",\"weight_bytes\":%zu,\"width\":%lld,\"rows\":%lld}\n",
                bytes, (long long)width, (long long)rows);
    for (int j = 0; j < 3; ++j) {
        const int k = counts[j];
        require(ggml_backend_graph_compute(backend, batch_graph[j]) == GGML_STATUS_SUCCESS,
                "batched projection check compute");
        std::vector<float> output(size_t(rows) * k);
        ggml_backend_tensor_get(batch_y[j], output.data(), 0,
                                output.size() * sizeof(float));
        double max_abs = 0;
        for (int i = 0; i < k; ++i) {
            int expected_choice = 0, actual_choice = 0;
            for (int row = 0; row < rows; ++row) {
                float expected = reference[i % 3][row];
                float actual = output[size_t(i) * rows + row];
                double error = std::abs(double(actual) - expected);
                require(std::isfinite(actual) && std::isfinite(expected)
                        && error <= 0.05 + 0.001 * std::abs(expected),
                        "predeclared batched projection numerical bound");
                max_abs = std::max(max_abs, error);
                if (expected > reference[i % 3][expected_choice]) expected_choice = row;
                if (actual > output[size_t(i) * rows + actual_choice]) actual_choice = row;
            }
            require(expected_choice == actual_choice, "batched greedy choice differs");
        }
        auto run = [&](bool batch) {
            auto start = std::chrono::steady_clock::now();
            if (batch) {
                require(ggml_backend_graph_compute(backend, batch_graph[j]) == GGML_STATUS_SUCCESS,
                        "batched projection timing compute");
            } else {
                for (int i = 0; i < k; ++i)
                    require(ggml_backend_graph_compute(backend, single_graph[i]) == GGML_STATUS_SUCCESS,
                            "single projection timing compute");
            }
            return std::chrono::duration<double, std::milli>(
                std::chrono::steady_clock::now() - start).count();
        };
        for (int warm = 0; warm < 12; ++warm) { run(false); run(true); }
        std::vector<double> serial, batch, differences;
        int wins = 0;
        for (int pair = 0; pair < 5; ++pair) {
            double a = 0, b = 0;
            if (pair % 2 == 0) { a = run(false); b = run(true); }
            else { b = run(true); a = run(false); }
            serial.push_back(a); batch.push_back(b); differences.push_back(a-b);
            wins += b < a;
            std::printf("{\"event\":\"pair\",\"k\":%d,\"pair\":%d,\"serial_ms\":%.6f,\"batch_ms\":%.6f}\n",
                        k, pair, a, b);
        }
        std::printf("{\"event\":\"summary\",\"k\":%d,\"max_abs\":%.9g,\"serial_median_ms\":%.6f,\"batch_median_ms\":%.6f,\"paired_serial_minus_batch_ms\":%.6f,\"batch_wins\":%d}\n",
                    k, max_abs, median(serial), median(batch), median(differences), wins);
    }
    ggml_backend_buffer_free(allocation);
    ggml_free(ctx);
    ggml_backend_free(backend);
    return 0;
}
