// Independent Metal graph argmax qualification; the Align runtime owns generation.
// clang++ -O2 -std=c++17 -I GGML/ggml/include -L BUNDLE -Wl,-rpath,BUNDLE \
//   -lggml -lggml-base scripts/bench-metal-ingraph-argmax.cpp -o bench-metal-ingraph-argmax
// bench-metal-ingraph-argmax PLUGIN CAPTURE_DIRECTORY
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
#include <vector>

static void require(bool yes, const char * message) {
    if (!yes) { std::fprintf(stderr, "%s\n", message); std::exit(1); }
}

static int32_t run(ggml_backend_t backend, const std::vector<float> & input) {
    auto ctx = ggml_init({ggml_tensor_overhead()*4 + ggml_graph_overhead(), nullptr, true});
    require(ctx != nullptr, "context allocation failed");
    auto source = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, input.size(), 1);
    auto result = ggml_argmax(ctx, source);
    auto graph = ggml_new_graph(ctx);
    ggml_build_forward_expand(graph, result);
    auto buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    require(buffer != nullptr, "tensor allocation failed");
    ggml_backend_tensor_set(source, input.data(), 0, input.size()*sizeof(float));
    require(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS,
            "graph computation failed");
    int32_t token = -2;
    ggml_backend_tensor_get(result, &token, 0, sizeof(token));
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
    return token;
}

static double timed_ms(ggml_backend_t backend, const std::vector<float> & input,
                       int32_t expected) {
    auto ctx = ggml_init({ggml_tensor_overhead()*4 + ggml_graph_overhead(), nullptr, true});
    require(ctx != nullptr, "timing context allocation failed");
    auto source = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, input.size(), 1);
    auto result = ggml_argmax(ctx, source);
    auto graph = ggml_new_graph(ctx);
    ggml_build_forward_expand(graph, result);
    auto buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    require(buffer != nullptr, "timing tensor allocation failed");
    ggml_backend_tensor_set(source, input.data(), 0, input.size()*sizeof(float));
    std::vector<double> samples;
    for (int i = 0; i < 55; ++i) {
        auto start = std::chrono::steady_clock::now();
        require(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS,
                "timing graph computation failed");
        int32_t token = -1;
        ggml_backend_tensor_get(result, &token, 0, sizeof(token));
        auto end = std::chrono::steady_clock::now();
        require(token == expected, "timing token mismatch");
        if (i >= 5) {
            samples.push_back(std::chrono::duration<double, std::milli>(end-start).count());
        }
    }
    std::sort(samples.begin(), samples.end());
    double median = (samples[24]+samples[25])*0.5;
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
    return median;
}

int main(int argc, char ** argv) {
    require(argc == 3 || (argc == 4 && std::strcmp(argv[3], "--timing") == 0),
            "usage: bench-metal-ingraph-argmax PLUGIN CAPTURE_DIRECTORY [--timing]");
    auto reg = ggml_backend_load(argv[1]);
    require(reg != nullptr, "plugin load failed");
    auto backend = ggml_backend_dev_init(ggml_backend_reg_dev_get(reg, 0), nullptr);
    require(backend != nullptr, "backend init failed");
    for (int capture = 0; capture < 3; ++capture) {
        char path[4096];
        require(std::snprintf(path, sizeof(path), "%s/%d-output.bin", argv[2], capture) <
                int(sizeof(path)), "capture path too long");
        std::ifstream stream(path, std::ios::binary | std::ios::ate);
        require(bool(stream) && stream.tellg() == std::streamoff(248320*sizeof(float)),
                "capture size mismatch");
        std::vector<float> row(248320);
        stream.seekg(0);
        stream.read(reinterpret_cast<char *>(row.data()), row.size()*sizeof(float));
        require(bool(stream), "capture read failed");
        int32_t expected = -1;
        float best = -INFINITY;
        for (size_t i = 0; i < row.size(); ++i) {
            require(std::isfinite(row[i]), "nonfinite real capture");
            if (row[i] > best) { best = row[i]; expected = int32_t(i); }
        }
        require(run(backend, row) == expected, "real capture mismatch");
        std::printf("capture=%d length=%zu token=%d PASS\n", capture, row.size(), expected);
        if (argc == 4 && capture == 0) {
            std::printf("steady_graph_compute_plus_scalar_read_median_ms=%.6f\n",
                        timed_ms(backend, row, expected));
        }
    }
    if (argc == 4) { ggml_backend_free(backend); return 0; }
    for (size_t length : {size_t(8192), size_t(248319), size_t(248320)}) {
        std::vector<float> row(length, -7.0f);
        row[3] = 10.0f; row[length - 1] = 10.0f;
        require(run(backend, row) == 3, "first-index tie mismatch");
        row[length - 1] = NAN;
        require(run(backend, row) == -1, "NaN refusal mismatch");
        row[length - 1] = INFINITY;
        require(run(backend, row) == -1, "infinity refusal mismatch");
        std::printf("edge_length=%zu tie/nonfinite PASS\n", length);
    }
    ggml_backend_free(backend);
}
