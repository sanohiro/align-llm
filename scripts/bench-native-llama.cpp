// Independent pinned llama.cpp reference for the native SwiGLU trial.
// Arguments: GGUF RENDERED_PROMPT EXPECTED_PROMPT_IDS OUTPUT_COUNT.
#include "llama.h"
#include "ggml-backend.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
static std::string read(const char * path) {
    std::ifstream input(path, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}
int main(int argc, char ** argv) {
    if (argc != 5) return 2;
    const int steps = std::atoi(argv[4]);
    if (steps < 1 || steps > 128) return 2;
    auto loading = std::chrono::steady_clock::now();
    const std::string rendered = read(argv[2]);
    const std::string expected = read(argv[3]);
    if (rendered.empty() || expected.empty()) return 2;
    llama_backend_init();
    if (!ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_GPU)) return 3;
    auto mp = llama_model_default_params();
    mp.n_gpu_layers = 99;
    llama_model * model = llama_model_load_from_file(argv[1], mp);
    if (!model) return 3;
    auto cp = llama_context_default_params();
    cp.n_ctx = 512; cp.n_batch = 512; cp.n_ubatch = 512;
    cp.n_threads = 4; cp.n_threads_batch = 4;
    cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED;
    llama_context * ctx = llama_init_from_model(model, cp);
    if (!ctx) return 4;
    const auto * vocab = llama_model_get_vocab(model);
    const int count = llama_vocab_n_tokens(vocab);
    std::printf("startup_ns=%lld\n", (long long)std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-loading).count());
    std::fflush(stdout);
    for (int iteration = 0; iteration < 3; ++iteration) {
        auto started = std::chrono::steady_clock::now();
        llama_memory_clear(llama_get_memory(ctx), true);
        std::vector<llama_token> prompt(512);
        int n = llama_tokenize(vocab, rendered.data(), static_cast<int32_t>(rendered.size()),
                               prompt.data(), static_cast<int32_t>(prompt.size()), false, true);
        if (n < 1 || n > 512) return 5;
        prompt.resize(n);
        std::vector<llama_token> expected_ids;
        for (size_t at = 0; at < expected.size();) {
            if (expected[at] >= '0' && expected[at] <= '9') {
                char * end = nullptr;
                long value = std::strtol(expected.c_str() + at, &end, 10);
                if (end == expected.c_str() + at) return 5;
                expected_ids.push_back(static_cast<llama_token>(value));
                at = static_cast<size_t>(end - expected.c_str());
            } else { ++at; }
        }
        if (expected_ids != prompt) { std::fprintf(stderr, "prompt IDs differ from Align\n"); return 6; }
        if (llama_decode(ctx, llama_batch_get_one(prompt.data(), n)) != 0) return 5;
        auto prefilled = std::chrono::steady_clock::now();
        auto first_done = prefilled;
        std::string pieces;
        std::vector<int> generated;
        for (int step = 0; step < steps; ++step) {
            const float * logits = llama_get_logits(ctx);
            if (!logits || !std::isfinite(logits[0])) return 5;
            llama_token next = static_cast<llama_token>(std::max_element(logits, logits + count) - logits);
            generated.push_back(next);
            char piece[4096];
            int bytes = llama_token_to_piece(vocab, next, piece, sizeof(piece), 0, true);
            if (bytes < 0) return 5;
            pieces.append(piece, bytes);
            if (step == 0) first_done = std::chrono::steady_clock::now();
            if (step != steps - 1 && llama_decode(ctx, llama_batch_get_one(&next, 1)) != 0) return 5;
        }
        auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - started).count();
        auto prefill_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(first_done - started).count();
        std::printf("iteration=%d prompt=%d elapsed_ns=%lld prefill_ns=%lld decode_ns=%lld ids=", iteration, n, (long long) ns, (long long) prefill_ns, (long long) (ns - prefill_ns));
        for (auto id : generated) std::printf("%d,", id);
        std::printf("\n");
    }
    llama_free(ctx); llama_model_free(model);
    return 0;
}
