// Connected native SwiGLU qualification on captured real FFNs or synthetic shapes.
// clang++ -O3 -std=c++17 -I GGML/ggml/include -L BUNDLE -Wl,-rpath,BUNDLE \
//   -lggml -lggml-base scripts/bench-native-swiglu.cpp -o bench-native-swiglu
// bench-native-swiglu PLUGIN CAPTURE_DIR LAYER WIDTH HIDDEN DOWN_GGML_TYPE
// CAPTURE_DIR '-' uses deterministic synthetic weights/activations.
#include "ggml.h"
#include "ggml-backend.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

static void require(bool condition, const char *what) {
    if (!condition) { std::fprintf(stderr, "%s\n", what); std::exit(1); }
}
static std::vector<unsigned char> bytes(const char *root, int layer, const char *role, size_t size) {
    char path[4096];
    require(std::snprintf(path, sizeof(path), "%s/%02d-%s.bin", root, layer, role) < int(sizeof(path)), "path too long");
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    require(bool(stream) && stream.tellg() == std::streamoff(size), "capture length mismatch");
    std::vector<unsigned char> value(size);
    stream.seekg(0); stream.read(reinterpret_cast<char *>(value.data()), size);
    require(bool(stream), "capture read failed");
    return value;
}
static void compare(const std::vector<float> &expected, const std::vector<float> &actual, const char *label) {
    double maximum = 0;
    for (size_t i = 0; i < expected.size(); ++i) {
        double error = std::abs(double(actual[i]) - expected[i]);
        maximum = std::max(maximum, error);
        require(std::isfinite(expected[i]) && std::isfinite(actual[i]) &&
                error <= 0.005 + 0.0005 * std::abs(expected[i]), "numeric tolerance exceeded");
    }
    std::printf("check=%s max_abs=%.9g count=%zu\n", label, maximum, expected.size());
}
static std::vector<float> read(ggml_tensor *t) {
    std::vector<float> out(ggml_nelements(t));
    ggml_backend_tensor_get(t, out.data(), 0, out.size() * sizeof(float));
    return out;
}
int main(int argc, char **argv) {
    require(argc == 7 || argc == 8, "usage: bench-native-swiglu PLUGIN CAPTURE_DIR LAYER WIDTH HIDDEN DOWN_TYPE");
    const bool check_only = argc == 8;
    const bool alias_input = check_only && std::string(argv[7]) == "--alias-input";
    require(!check_only || alias_input || std::string(argv[7]) == "--check-only", "invalid check mode");
    const int layer = std::atoi(argv[3]), width = std::atoi(argv[4]), hidden = std::atoi(argv[5]);
    const int dt = std::atoi(argv[6]);
    require(layer >= 0 && layer < 128 && width > 0 && width <= 65536 && width % 32 == 0 &&
            hidden > 0 && hidden <= 65536 && hidden % 32 == 0 && (dt == 2 || dt == 3), "invalid geometry/type");
    auto reg = ggml_backend_load(argv[1]); require(reg, "plugin load failed");
    auto backend = ggml_backend_dev_init(ggml_backend_reg_dev_get(reg, 0), nullptr);
    require(backend, "device unavailable");
    auto ctx = ggml_init({ggml_tensor_overhead()*64 + 4*ggml_graph_overhead_custom(64, false), nullptr, true});
    require(ctx, "context failed");
    auto wg = ggml_new_tensor_2d(ctx, GGML_TYPE_Q4_0, width, hidden);
    auto wu = ggml_new_tensor_2d(ctx, GGML_TYPE_Q4_0, width, hidden);
    auto wd = ggml_new_tensor_2d(ctx, ggml_type(dt), hidden, width);
    auto x = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, width);
    ggml_tensor *gated[2], *down[2]; ggml_cgraph *graphs[2][2];
    for (int arm = 0; arm < 2; ++arm) {
        auto g = ggml_mul_mat(ctx, wg, x); auto u = ggml_mul_mat(ctx, wu, x);
        if (arm) ggml_set_name(g, "align_native_q40_swiglu");
        gated[arm] = ggml_swiglu_split(ctx, g, u);
        down[arm] = ggml_mul_mat(ctx, wd, gated[arm]);
        for (int full = 0; full < 2; ++full) {
            graphs[arm][full] = ggml_new_graph_custom(ctx, 64, false);
            ggml_build_forward_expand(graphs[arm][full], full ? down[arm] : gated[arm]);
        }
    }
    auto buffer = ggml_backend_alloc_ctx_tensors(ctx, backend); require(buffer, "allocation failed");
    const bool synthetic = std::string(argv[2]) == "-";
    for (auto pair : {std::make_pair(wg, "gate"), std::make_pair(wu, "up"), std::make_pair(wd, "down"), std::make_pair(x, "input")}) {
        auto t = pair.first;
        std::vector<unsigned char> data(ggml_nbytes(t));
        if (!synthetic) data = bytes(argv[2], layer, pair.second, data.size());
        else if (t == x) {
            std::vector<float> input(width);
            for (int i=0; i<width; ++i) input[i] = std::sin(i*0.013f);
            ggml_backend_tensor_set(t, input.data(), 0, data.size()); continue;
        } else {
            const size_t block = dt == 3 && t == wd ? 20 : 18;
            for (size_t at=0; at<data.size(); at+=block) {
                data[at]=0; data[at+1]=0x20; // finite f16 scale
                for(size_t j=(block==20 ? 4 : 2);j<block;++j) data[at+j]=(at*7+j*13)%256;
            }
        }
        ggml_backend_tensor_set(t, data.data(), 0, data.size());
    }
    auto run = [&](int arm, int full) {
        auto start=std::chrono::steady_clock::now();
        require(ggml_backend_graph_compute(backend, graphs[arm][full]) == GGML_STATUS_SUCCESS, "compute failed");
        return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    };
    if (alias_input) {
        require(width == hidden && synthetic, "alias owner requires square synthetic geometry");
        gated[1]->data = x->data;
        gated[1]->buffer = x->buffer;
    }
    for(int i=0;i<(check_only ? 1 : 12);++i){run(0,1);run(1,1);}
    compare(read(gated[0]),read(gated[1]),"gated");
    compare(read(down[0]),read(down[1]),"down");
    if (!synthetic) {
        for(auto pair : {std::make_pair(gated[0],"gated"),std::make_pair(down[0],"output")}) {
            auto raw=bytes(argv[2],layer,pair.second,ggml_nbytes(pair.first));
            std::vector<float> expected(raw.size()/4);
            std::memcpy(expected.data(),raw.data(),raw.size());
            compare(expected,read(pair.first),"captured");
        }
    }
    std::printf("width=%d hidden=%d down_type=%d device_bytes=%zu\n",width,hidden,dt,ggml_backend_buffer_get_size(buffer));
    if (!check_only) for(int full=0;full<2;++full) for(int pair=0;pair<5;++pair){
        double ms[2]={0,0};
        for(int i=0;i<20;++i)for(int j=0;j<2;++j){int arm=(pair+j)%2;ms[arm]+=run(arm,full);}
        std::printf("stage=%s pair=%d control_ms=%.6f native_ms=%.6f\n",full?"ffn":"gated",pair,ms[0]/20,ms[1]/20);
    }
    ggml_backend_buffer_free(buffer);ggml_free(ctx);ggml_backend_free(backend);
}
