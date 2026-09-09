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
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

using json = nlohmann::ordered_json;
namespace fs = std::filesystem;

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

static std::string piece(const llama_vocab *vocab, llama_token token, bool special) {
    std::vector<char> bytes(65536);
    int size = llama_token_to_piece(vocab, token, bytes.data(), int(bytes.size()), 0, special);
    assert(size >= 0 && size <= int(bytes.size()));
    return std::string(bytes.data(), size);
}

static void decode(llama_context *ctx, const std::vector<llama_token> &tokens, int position) {
    assert(!tokens.empty() && tokens.size() <= 2048);
    auto batch = llama_batch_init(int(tokens.size()), 0, 1);
    batch.n_tokens = int(tokens.size());
    for (int i = 0; i < batch.n_tokens; ++i) {
        batch.token[i] = tokens[i]; batch.pos[i] = position + i;
        batch.n_seq_id[i] = 1; batch.seq_id[i][0] = 0;
        batch.logits[i] = i + 1 == batch.n_tokens;
    }
    assert(llama_decode(ctx, batch) == 0);
    llama_batch_free(batch);
}

int main(int argc, char **argv) {
    assert(argc == 2 && fs::file_size(argv[1]) <= 1048576);
    std::ifstream input(argv[1]); auto config = json::parse(input);
    auto registry = ggml_backend_load(config.at("plugin_path").get<std::string>().c_str());
    assert(registry && ggml_backend_reg_dev_count(registry) == 1);
    ggml_backend_dev_t devices[] = {ggml_backend_reg_dev_get(registry, 0), nullptr};
    assert(ggml_backend_dev_type(devices[0]) == GGML_BACKEND_DEVICE_TYPE_GPU);
    assert(config.at("device") == ggml_backend_dev_name(devices[0]));
    const auto architecture = config.at("architecture").get<std::string>();
    assert(architecture == "qwen2" || architecture == "olmoe");
    assert(config.at("requests").is_array() && !config.at("requests").empty() && config.at("requests").size() <= 32);
    llama_backend_init();
    auto mp = llama_model_default_params(); mp.n_gpu_layers = -1; mp.devices = devices;
    llama_model_tensor_buft_override overrides[] = {
        {"token_embd.weight", ggml_backend_dev_buffer_type(devices[0])}, {nullptr, nullptr}};
    mp.tensor_buft_overrides = overrides;
    auto model = llama_model_load_from_file(config.at("model_path").get<std::string>().c_str(), mp);
    assert(model && llama_model_n_ctx_train(model) >= 2304);
    auto vocabulary = llama_model_get_vocab(model);
    int count = llama_vocab_n_tokens(vocabulary);
    auto cp = llama_context_default_params();
    cp.n_ctx = 2304; cp.n_batch = 2048; cp.n_ubatch = 128;
    cp.type_k = cp.type_v = GGML_TYPE_F32; cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED;
    cp.n_threads = cp.n_threads_batch = 4;
    auto ctx = llama_init_from_model(model, cp); assert(ctx);
    std::vector<llama_token> previous;
    for (const auto &request : config.at("requests")) {
        const auto system = request.at("system").get<std::string>();
        const auto user = request.at("user").get<std::string>();
        std::string rendered;
        if (architecture == "olmoe") {
            rendered = piece(vocabulary, llama_vocab_bos(vocabulary), true) +
                "<|system|>\n" + system + "\n<|user|>\n" + user + "\n<|assistant|>\n";
        } else {
            rendered = "<|im_start|>system\n" + system + "<|im_end|>\n<|im_start|>user\n" +
                user + "<|im_end|>\n<|im_start|>assistant\n";
        }
        assert(rendered.size() <= 1048576 && rendered.find('\0') == std::string::npos);
        std::vector<llama_token> prompt(2048);
        int length = llama_tokenize(vocabulary, rendered.data(), int(rendered.size()),
                                    prompt.data(), int(prompt.size()), false, true);
        assert(length > 0 && length <= 2048); prompt.resize(length);
        int maximum = request.at("max_tokens").get<int>(); assert(maximum >= 1 && maximum <= 128);
        bool seeded = !request.at("seed").is_null();
        assert(!seeded || architecture == "olmoe");
        Random random(seeded ? uint64_t(request.at("seed").get<int64_t>()) : 0);
        size_t common = 0;
        while (common < previous.size() && common + 1 < prompt.size() && previous[common] == prompt[common]) ++common;
        assert(llama_memory_seq_rm(llama_get_memory(ctx), 0, int(common), -1));
        decode(ctx, std::vector<llama_token>(prompt.begin() + common, prompt.end()), int(common));
        std::vector<llama_token> generated;
        std::string text;
        int position = int(prompt.size());
        for (int step = 0; step < maximum; ++step) {
            auto logits = llama_get_logits_ith(ctx, -1); assert(logits);
            auto token = sample(logits, count, seeded, random); generated.push_back(token);
            if (llama_vocab_is_eog(vocabulary, token)) break;
            text += piece(vocabulary, token, false); assert(text.size() <= 262144);
            if (step + 1 == maximum) break;
            decode(ctx, {token}, position++);
        }
        previous = prompt;
        previous.insert(previous.end(), generated.begin(), generated.end() - 1);
        bool eog = llama_vocab_is_eog(vocabulary, generated.back());
        json result{{"output", text}, {"prompt_tokens", prompt.size()},
                    {"completion_tokens", generated.size() - (eog ? 1 : 0)},
                    {"prompt_ids", prompt}, {"token_ids", generated}, {"reused_tokens", common}};
        std::cout << result.dump() << std::endl;
    }
    llama_free(ctx); llama_model_free(model); llama_backend_free();
}
