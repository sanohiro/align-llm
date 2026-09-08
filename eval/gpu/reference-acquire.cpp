// Independent acquisition from the pinned llama.cpp model graph; not a qualifier verdict.
#include "llama.h"
#include "ggml-backend.h"
#include "nlohmann/json.hpp"
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#ifdef NDEBUG
#error This diagnostic requires active assertions.
#endif
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <numeric>
#include <string>
#include <vector>

using json = nlohmann::ordered_json;
namespace fs = std::filesystem;
static constexpr uint64_t ceiling = uint64_t(4) << 30;

struct Random {
    std::array<uint64_t, 4> s;
    explicit Random(uint64_t seed) {
        for (auto &word : s) {
            seed += UINT64_C(0x9e3779b97f4a7c15);
            auto z = seed;
            z = (z ^ (z >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
            z = (z ^ (z >> 27)) * UINT64_C(0x94d049bb133111eb);
            word = z ^ (z >> 31);
        }
        if (s == std::array<uint64_t, 4>{}) s[0] = 1;
    }
    static uint64_t rot(uint64_t v, int n) { return (v << n) | (v >> (64 - n)); }
    uint64_t next() {
        uint64_t result = rot(s[0] + s[3], 23) + s[0], t = s[1] << 17;
        s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3];
        s[2] ^= t; s[3] = rot(s[3], 45);
        return result;
    }
    uint64_t bounded(uint64_t range) {
        assert(range > 0);
        for (;;) {
            __uint128_t product = __uint128_t(next()) * range;
            if (uint64_t(product) >= -range % range) return uint64_t(product >> 64);
        }
    }
};

static llama_token sample(const float *logits, int count, bool seeded, Random &random) {
    std::vector<int> ids(count);
    std::iota(ids.begin(), ids.end(), 0);
    for (int i = 0; i < count; ++i) assert(std::isfinite(logits[i]));
    size_t k = std::min(size_t(count), size_t(40));
    std::partial_sort(ids.begin(), ids.begin() + k, ids.end(), [&](int a, int b) {
        return logits[a] > logits[b] || (logits[a] == logits[b] && a < b);
    });
    if (!seeded) return ids[0];
    std::vector<double> raw(k);
    double total = 0, cumulative = 0, maximum = logits[ids[0]];
    for (size_t i = 0; i < k; ++i) {
        raw[i] = std::pow(2.718281828459045, double(logits[ids[i]]) - maximum);
        total += raw[i];
    }
    size_t p = k;
    for (size_t i = 0; i < k; ++i) {
        cumulative += raw[i];
        if (cumulative >= total * .95) { p = i + 1; break; }
    }
    size_t kept = 0;
    while (kept < p && raw[kept] >= raw[0] * .05) ++kept;
    assert(kept > 0);
    std::vector<uint64_t> weights(kept);
    uint64_t sum = 0;
    for (size_t i = 0; i < kept; ++i) {
        weights[i] = uint64_t(std::round(std::pow(2.718281828459045,
            (double(logits[ids[i]]) - maximum) / .3) * 1000000000.0));
        assert(weights[i] > 0); sum += weights[i];
    }
    auto draw = random.bounded(sum);
    for (size_t i = 0; i < kept; ++i) {
        if (draw < weights[i]) return ids[i];
        draw -= weights[i];
    }
    std::abort();
}

struct Capture {
    fs::path root;
    std::ofstream index;
    uint64_t bytes = 0, ordinal = 0;
    int step = 0;
    void write(const std::string &name, int type, std::array<int64_t, 4> shape,
               const void *data, size_t size) {
        assert(size > 0 && size <= (uint64_t(64) << 20) && bytes <= ceiling - size);
        if (type == GGML_TYPE_F32) {
            for (size_t offset = 0; offset < size; offset += 4) {
                float value; std::memcpy(&value, static_cast<const char *>(data) + offset, 4);
                assert(std::isfinite(value));
            }
        }
        auto file = std::to_string(ordinal++) + ".bin";
        std::ofstream out(root / file, std::ios::binary);
        out.write(static_cast<const char *>(data), size); out.close(); assert(out);
        index << json{{"file", file}, {"step", step}, {"name", name},
            {"type", type}, {"shape", shape}, {"bytes", size}}.dump() << '\n';
        index.flush(); assert(index); bytes += size;
    }
};

static bool selected_name(const std::string &name) {
    for (const char *prefix : {"l_out-", "ffn_moe_probs-", "ffn_moe_topk-", "ffn_moe_weights-"}) {
        std::string p(prefix);
        if (name.compare(0, p.size(), p) == 0 && name.size() > p.size() &&
            name.find_first_not_of("0123456789", p.size()) == std::string::npos) return true;
    }
    return false;
}

static bool callback(ggml_tensor *t, bool ask, void *opaque) {
    std::string name(ggml_get_name(t));
    // The highest layer has zero output columns on a non-final microbatch.
    bool wanted = selected_name(name) && ggml_nelements(t) > 0;
    if (ask || !wanted) return wanted;
    assert(t->type == GGML_TYPE_F32 || t->type == GGML_TYPE_I32);
    assert(ggml_nbytes(t) <= (uint64_t(64) << 20));
    std::vector<unsigned char> raw(ggml_nbytes(t)), packed;
    ggml_backend_tensor_get(t, raw.data(), 0, raw.size());
    packed.reserve(size_t(ggml_nelements(t)) * 4);
    for (int64_t w = 0; w < t->ne[3]; ++w) for (int64_t z = 0; z < t->ne[2]; ++z)
        for (int64_t y = 0; y < t->ne[1]; ++y) for (int64_t x = 0; x < t->ne[0]; ++x) {
            size_t offset = x*t->nb[0] + y*t->nb[1] + z*t->nb[2] + w*t->nb[3];
            assert(offset + 4 <= raw.size());
            packed.insert(packed.end(), raw.begin() + offset, raw.begin() + offset + 4);
        }
    static_cast<Capture *>(opaque)->write(name, int(t->type),
        {t->ne[0], t->ne[1], t->ne[2], t->ne[3]}, packed.data(), packed.size());
    return true;
}

int main(int argc, char **argv) {
    assert(argc == 2 && fs::file_size(argv[1]) <= 1048576);
    std::ifstream input(argv[1]); auto request = json::parse(input);
    assert(request.is_object() && request.size() == 6);
    for (const char *key : {"model_path", "plugin_path", "output_root"}) {
        assert(request.at(key).is_string());
        auto path = request.at(key).get<std::string>();
        assert(!path.empty() && path.size() <= 4096 && path.find('\0') == std::string::npos);
    }
    assert(request.at("prompt_token_ids").is_array() && request.at("prompt_token_ids").size() <= 2048);
    for (const auto &id : request.at("prompt_token_ids"))
        assert(id.is_number_integer() && id >= 0 && id <= std::numeric_limits<int32_t>::max());
    assert(request.at("maximum_tokens").is_number_integer() && request.at("maximum_tokens") >= 1 && request.at("maximum_tokens") <= 128);
    assert(request.at("seed").is_null() || (request.at("seed").is_number_integer() &&
        (!request.at("seed").is_number_unsigned() || request.at("seed") <= std::numeric_limits<int64_t>::max())));
    auto prompt = request.at("prompt_token_ids").get<std::vector<llama_token>>();
    auto maximum = request.at("maximum_tokens").get<int>();
    assert(!prompt.empty() && prompt.size() <= 2048 && maximum >= 1 && maximum <= 128);
    bool seeded = !request.at("seed").is_null();
    Random random(seeded ? uint64_t(request.at("seed").get<int64_t>()) : 0);
    fs::path root(request.at("output_root").get<std::string>());
    assert(root.is_absolute() && fs::is_directory(root) && fs::is_empty(root));
    Capture capture{root, std::ofstream(root / "index.jsonl")}; assert(capture.index);
    auto registry = ggml_backend_load(request.at("plugin_path").get<std::string>().c_str());
    assert(registry && ggml_backend_reg_dev_count(registry) == 1);
    ggml_backend_dev_t devices[] = {ggml_backend_reg_dev_get(registry, 0), nullptr};
    assert(ggml_backend_dev_type(devices[0]) == GGML_BACKEND_DEVICE_TYPE_GPU);
    llama_backend_init();
    auto mp = llama_model_default_params(); mp.n_gpu_layers = -1; mp.devices = devices;
    llama_model_tensor_buft_override overrides[] = {
        {"token_embd.weight", ggml_backend_dev_buffer_type(devices[0])}, {nullptr, nullptr}};
    mp.tensor_buft_overrides = overrides;
    auto model = llama_model_load_from_file(request.at("model_path").get<std::string>().c_str(), mp);
    assert(model);
    auto vocabulary = llama_model_get_vocab(model);
    int count = llama_vocab_n_tokens(vocabulary);
    for (auto id : prompt) assert(id >= 0 && id < count);
    assert(llama_model_n_ctx_train(model) > 0 &&
        prompt.size() + maximum <= size_t(llama_model_n_ctx_train(model)));
    auto cp = llama_context_default_params();
    cp.n_ctx = uint32_t(((prompt.size() + maximum + 255) / 256) * 256);
    cp.n_batch = cp.n_ctx; cp.n_ubatch = 128;
    cp.type_k = cp.type_v = GGML_TYPE_F32;
    cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;
    cp.n_threads = cp.n_threads_batch = 4;
    cp.cb_eval = callback; cp.cb_eval_user_data = &capture;
    auto ctx = llama_init_from_model(model, cp); assert(ctx);
    assert(llama_decode(ctx, llama_batch_get_one(prompt.data(), int(prompt.size()))) == 0);
    std::vector<llama_token> generated;
    std::string text;
    for (int step = 0; step < maximum; ++step) {
        const float *logits = llama_get_logits_ith(ctx, -1); assert(logits);
        capture.write("logits", GGML_TYPE_F32, {count, 1, 1, 1}, logits, size_t(count) * 4);
        auto token = sample(logits, count, seeded, random); generated.push_back(token);
        if (llama_vocab_is_eog(vocabulary, token)) break;
        std::vector<char> piece(65536);
        int size = llama_token_to_piece(vocabulary, token, piece.data(), int(piece.size()), 0, false);
        assert(size >= 0 && size <= int(piece.size())); text.append(piece.data(), size);
        if (step + 1 == maximum) break;
        capture.step = step + 1;
        assert(llama_decode(ctx, llama_batch_get_one(&token, 1)) == 0);
    }
    // One independent teacher-forced tail row also covers a sampled immediate EOG.
    capture.step = int(generated.size());
    auto last = generated.back();
    assert(llama_decode(ctx, llama_batch_get_one(&last, 1)) == 0);
    auto tail = llama_get_logits_ith(ctx, -1); assert(tail);
    capture.write("logits", GGML_TYPE_F32, {count, 1, 1, 1}, tail, size_t(count) * 4);
    json result{{"token_ids", generated}, {"text", text}, {"prompt_ids", prompt},
        {"tensor_records", capture.ordinal}, {"tensor_bytes", capture.bytes}};
    std::ofstream output(root / "production.json"); output << result.dump() << '\n';
    output.close(); assert(output); capture.index.close(); assert(capture.index);
    llama_free(ctx); llama_model_free(model); llama_backend_free();
    std::puts("Independent GPU acquisition complete; no qualification verdict.");
    return 0;
}
