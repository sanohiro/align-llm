// Independent pinned llama.cpp greedy reference for the Qwen3.5 lookup trial.
// Arguments: GGUF PROMPT_IDS_JSON EXPECTED_IDS_JSON.
#include "llama.h"
#include "ggml-backend.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

static std::vector<llama_token> read_ids(const char * path) {
    std::ifstream source(path, std::ios::binary);
    std::string input(std::istreambuf_iterator<char>{source}, {});
    std::vector<llama_token> ids;
    for (size_t at = 0; at < input.size();) {
        if (input[at] >= '0' && input[at] <= '9') {
            char * end = nullptr;
            const long value = std::strtol(input.c_str() + at, &end, 10);
            if (end == input.c_str() + at || value < 0 || value > INT32_MAX) return {};
            ids.push_back(static_cast<llama_token>(value));
            at = static_cast<size_t>(end - input.c_str());
        } else if (input[at] == '[' || input[at] == ']' || input[at] == ',' ||
                   input[at] == ' ' || input[at] == '\n') {
            ++at;
        } else {
            return {};
        }
    }
    return ids;
}

int main(int argc, char ** argv) {
    if (argc != 4) return 2;
    const auto prompt = read_ids(argv[2]);
    const auto expected = read_ids(argv[3]);
    if (prompt.empty() || expected.empty() || prompt.size() + expected.size() > 512) return 2;
    const auto loading = std::chrono::steady_clock::now();
    llama_backend_init();
    if (!ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_GPU)) return 3;
    auto mp = llama_model_default_params();
    mp.n_gpu_layers = 99;
    llama_model * model = llama_model_load_from_file(argv[1], mp);
    if (!model) return 3;
    auto cp = llama_context_default_params();
    cp.n_ctx = 512;
    cp.n_batch = 512;
    cp.n_ubatch = 512;
    cp.n_threads = 4;
    cp.n_threads_batch = 4;
    cp.type_k = GGML_TYPE_F16;
    cp.type_v = GGML_TYPE_F16;
    cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED;
    llama_context * ctx = llama_init_from_model(model, cp);
    if (!ctx) { llama_model_free(model); return 4; }
    const auto ready = std::chrono::steady_clock::now();
    const auto started = ready;
    std::vector<llama_token> copy = prompt;
    if (llama_decode(ctx, llama_batch_get_one(copy.data(), copy.size())) != 0) return 5;
    const auto prefilled = std::chrono::steady_clock::now();
    const int vocab = llama_vocab_n_tokens(llama_model_get_vocab(model));
    for (size_t step = 0; step < expected.size(); ++step) {
        const float * logits = llama_get_logits(ctx);
        if (!logits || !std::isfinite(logits[0])) return 5;
        auto token = static_cast<llama_token>(
            std::max_element(logits, logits + vocab) - logits);
        if (token != expected[step]) {
            std::fprintf(stderr, "greedy ID mismatch at output %zu: %d != %d\n",
                         step, token, expected[step]);
            return 6;
        }
        if (step + 1 < expected.size() &&
            llama_decode(ctx, llama_batch_get_one(&token, 1)) != 0) return 5;
    }
    const auto finished = std::chrono::steady_clock::now();
    const auto ns = [](auto a, auto b) {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(b - a).count();
    };
    std::printf("{\"startup_load_ns\":%lld,\"generation_ns\":%lld,"
                "\"prefill_ns\":%lld,\"decode_ns\":%lld,"
                "\"prompt_tokens\":%zu,\"generated_tokens\":%zu}\n",
                static_cast<long long>(ns(loading, ready)),
                static_cast<long long>(ns(started, finished)),
                static_cast<long long>(ns(started, prefilled)),
                static_cast<long long>(ns(prefilled, finished)),
                prompt.size(), expected.size());
    llama_free(ctx);
    llama_model_free(model);
    llama_backend_free();
    return 0;
}
