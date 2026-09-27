// Focused correctness owner for the pinned Metal contiguous F32 copy variant.
// Build against the pinned ggml headers and one selected Metal bundle:
// clang++ -O2 -std=c++17 -I GGML/ggml/include -L BUNDLE -Wl,-rpath,BUNDLE \
//   -lggml -lggml-base scripts/metal-linear-copy-geometry.cpp -o /tmp/metal-copy-geometry
// Run the same executable once with the control plugin and once with the trial plugin.

#include "ggml.h"
#include "ggml-backend.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

struct Case {
    const char * name;
    int64_t n0, n1, n2, n3;
    int64_t source_row, destination_row;
    int64_t source_offset, destination_offset;
};

static void require(bool value, const char * message) {
    if (!value) {
        std::fprintf(stderr, "metal-linear-copy-geometry: %s\n", message);
        std::exit(1);
    }
}

static uint32_t bits(float value) {
    uint32_t result;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

static void check(ggml_backend_t backend, const Case & test) {
    const int64_t count = test.n0 * test.n1 * test.n2 * test.n3;
    const int64_t source_size = test.source_offset +
        test.source_row * test.n1 * test.n2 * test.n3;
    const int64_t destination_size = test.destination_offset +
        test.destination_row * test.n1 * test.n2 * test.n3;
    require(count > 0 && source_size > 0 && destination_size > 0,
            "invalid fixture extent");

    std::vector<float> source(source_size);
    std::vector<float> destination(destination_size, -999.0f);
    std::vector<float> expected = destination;
    for (int64_t i = 0; i < source_size; ++i) {
        source[i] = float((i * 257) % 65521 - 32760) / 1024.0f;
    }
    for (int64_t i3 = 0; i3 < test.n3; ++i3) {
        for (int64_t i2 = 0; i2 < test.n2; ++i2) {
            for (int64_t i1 = 0; i1 < test.n1; ++i1) {
                for (int64_t i0 = 0; i0 < test.n0; ++i0) {
                    const int64_t source_index = test.source_offset +
                        ((i3 * test.n2 + i2) * test.n1 + i1) * test.source_row + i0;
                    const int64_t destination_index = test.destination_offset +
                        ((i3 * test.n2 + i2) * test.n1 + i1) * test.destination_row + i0;
                    expected[destination_index] = source[source_index];
                }
            }
        }
    }

    ggml_init_params params = {
        ggml_tensor_overhead() * 16 + ggml_graph_overhead_custom(16, false),
        nullptr, true
    };
    ggml_context * ctx = ggml_init(params);
    require(ctx != nullptr, "ggml context allocation failed");
    ggml_tensor * source_base = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, source_size);
    ggml_tensor * destination_base = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, destination_size);
    ggml_tensor * source_view = ggml_view_4d(ctx, source_base,
        test.n0, test.n1, test.n2, test.n3,
        test.source_row * 4, test.source_row * test.n1 * 4,
        test.source_row * test.n1 * test.n2 * 4, test.source_offset * 4);
    ggml_tensor * destination_view = ggml_view_4d(ctx, destination_base,
        test.n0, test.n1, test.n2, test.n3,
        test.destination_row * 4, test.destination_row * test.n1 * 4,
        test.destination_row * test.n1 * test.n2 * 4, test.destination_offset * 4);
    ggml_tensor * copied = ggml_cpy(ctx, source_view, destination_view);
    ggml_cgraph * graph = ggml_new_graph_custom(ctx, 16, false);
    ggml_build_forward_expand(graph, copied);
    ggml_backend_buffer_t buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
    require(buffer != nullptr, "Metal tensor allocation failed");
    ggml_backend_tensor_set(source_base, source.data(), 0, source.size() * sizeof(float));
    ggml_backend_tensor_set(destination_base, destination.data(), 0,
                            destination.size() * sizeof(float));
    require(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS,
            "Metal copy graph failed");
    ggml_backend_tensor_get(destination_base, destination.data(), 0,
                            destination.size() * sizeof(float));
    for (int64_t i = 0; i < destination_size; ++i) {
        if (bits(destination[i]) != bits(expected[i])) {
            std::fprintf(stderr, "case=%s index=%lld actual=%08x expected=%08x\n",
                         test.name, static_cast<long long>(i), bits(destination[i]),
                         bits(expected[i]));
            std::exit(1);
        }
    }
    std::printf("{\"case\":\"%s\",\"elements\":%lld,\"source_contiguous\":%s,"
                "\"destination_contiguous\":%s,\"checked_destination_elements\":%lld,"
                "\"status\":\"PASS\"}\n", test.name,
                static_cast<long long>(count),
                test.source_row == test.n0 ? "true" : "false",
                test.destination_row == test.n0 ? "true" : "false",
                static_cast<long long>(destination_size));
    ggml_backend_buffer_free(buffer);
    ggml_free(ctx);
}

int main(int argc, char ** argv) {
    require(argc == 2, "usage: metal-copy-geometry LIBGGML_METAL_SO");
    ggml_backend_reg_t reg = ggml_backend_load(argv[1]);
    require(reg != nullptr, "pinned Metal plugin load failed");
    ggml_backend_dev_t device = ggml_backend_reg_dev_get(reg, 0);
    ggml_backend_t backend = ggml_backend_dev_init(device, nullptr);
    require(backend != nullptr, "Metal backend initialization failed");
    const Case cases[] = {
        {"below_threshold", 511, 513, 1, 1, 511, 511, 0, 0},
        {"at_threshold", 512, 512, 1, 1, 512, 512, 0, 0},
        {"contiguous_4d", 64, 64, 8, 8, 64, 64, 0, 0},
        {"offset_contiguous", 512, 512, 1, 1, 512, 512, 64, 128},
        {"strided_source", 512, 512, 1, 1, 1024, 512, 0, 0},
        {"strided_destination", 512, 512, 1, 1, 512, 1024, 0, 0},
    };
    for (const Case & test : cases) check(backend, test);
    ggml_backend_free(backend);
    return 0;
}
