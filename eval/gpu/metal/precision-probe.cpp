// Isolate CPU/Metal arithmetic differences without application graphs or Align code.
// See README.md for the exact pinned libraries, build command and observed results.
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-alloc.h"
#include "ggml-cpu.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <vector>

static std::vector<float> run(ggml_backend_t backend, ggml_type type,
                             const std::vector<float>& weights,
                             const std::vector<float>& inputs, int columns) {
    auto context = ggml_init({4 * 1024 * 1024, nullptr, true});
    assert(context);
    auto a = ggml_new_tensor_2d(context, type, 256, 32);
    auto b = ggml_new_tensor_2d(context, GGML_TYPE_F32, 256, columns);
    auto c = ggml_mul_mat(context, a, b);
    auto graph = ggml_new_graph(context);
    ggml_build_forward_expand(graph, c);
    auto buffer = ggml_backend_alloc_ctx_tensors(context, backend);
    assert(buffer);
    std::vector<unsigned char> packed(ggml_nbytes(a));
    const auto bytes = ggml_quantize_chunk(type, weights.data(), packed.data(),
                                          0, 32, 256, nullptr);
    assert(bytes == packed.size());
    ggml_backend_tensor_set(a, packed.data(), 0, packed.size());
    ggml_backend_tensor_set(b, inputs.data(), 0, inputs.size() * sizeof(float));
    const auto status = ggml_backend_graph_compute(backend, graph);
    assert(status == GGML_STATUS_SUCCESS);
    ggml_backend_synchronize(backend);
    std::vector<float> output(32 * columns);
    ggml_backend_tensor_get(c, output.data(), 0, output.size() * sizeof(float));
    ggml_backend_buffer_free(buffer);
    ggml_free(context);
    return output;
}

int main(int argc, char** argv) {
    assert(argc == 2);
    auto registry = ggml_backend_load(argv[1]);
    assert(registry && ggml_backend_reg_dev_count(registry) == 1);
    auto gpu = ggml_backend_dev_init(ggml_backend_reg_dev_get(registry, 0), nullptr);
    auto cpu = ggml_backend_cpu_init();
    assert(gpu && cpu);
    std::vector<float> weights(256 * 32);
    for (size_t i = 0; i < weights.size(); ++i) {
        weights[i] = std::sin(float(i) * .173f) * .7f;
    }
    for (int columns : {1, 20}) {
        std::vector<float> inputs(256 * columns);
        for (size_t i = 0; i < inputs.size(); ++i) {
            inputs[i] = std::cos(float(i) * .113f) * 1.3f;
        }
        for (auto type : {GGML_TYPE_F32, GGML_TYPE_Q4_K, GGML_TYPE_Q6_K}) {
            const auto reference = run(cpu, type, weights, inputs, columns);
            const auto candidate = run(gpu, type, weights, inputs, columns);
            float maximum = 0;
            int mismatches = 0;
            for (size_t i = 0; i < reference.size(); ++i) {
                assert(std::isfinite(reference[i]) && std::isfinite(candidate[i]));
                const float difference = std::abs(reference[i] - candidate[i]);
                maximum = std::fmax(maximum, difference);
                const float scale = std::fmax(std::abs(reference[i]), std::abs(candidate[i]));
                mismatches += difference > std::fmax(.001f, .001f * scale);
            }
            std::printf("type=%s tokens=%d max_abs=%.9g mismatch=%d/%zu\n",
                        ggml_type_name(type), columns, maximum, mismatches, reference.size());
        }
    }
    ggml_backend_free(cpu);
    ggml_backend_free(gpu);
}
