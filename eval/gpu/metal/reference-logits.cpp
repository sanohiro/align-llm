// Independent diagnostic using pinned llama.cpp, with every model tensor on one GPU.
// Arguments: GGUF, plugin, comma-separated prompt IDs, forced IDs, raw F32 output.
// Output contains the prompt logits followed by one vocabulary row per forced token.
#include "llama.h"
#include "ggml-backend.h"
#include <cassert>
#include <cerrno>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <vector>

static std::vector<llama_token> tokens(const char *text) {
    std::vector<llama_token> result;
    assert(text != nullptr && *text != '\0');
    for (;;) {
        char *end = nullptr;
        errno = 0;
        assert(*text >= '0' && *text <= '9');
        long value = std::strtol(text, &end, 10);
        assert(errno == 0 && end != text && value >= 0 && value <= INT_MAX);
        result.push_back(static_cast<llama_token>(value));
        assert(result.size() <= 4096);
        if (*end == '\0') { break; }
        assert(*end == ',');
        text = end + 1;
    }
    return result;
}

int main(int argc, char **argv) {
    assert(argc == 6);
    auto prompt = tokens(argv[3]);
    auto forced = tokens(argv[4]);
    auto registry = ggml_backend_load(argv[2]);
    assert(registry != nullptr && ggml_backend_reg_dev_count(registry) == 1);
    ggml_backend_dev_t devices[] = {ggml_backend_reg_dev_get(registry, 0), nullptr};
    assert(ggml_backend_dev_type(devices[0]) == GGML_BACKEND_DEVICE_TYPE_GPU);
    llama_backend_init();
    auto mp = llama_model_default_params();
    mp.n_gpu_layers = -1;
    mp.devices = devices;
    // Upstream normally leaves embedding lookup on CPU even with every layer offloaded.
    llama_model_tensor_buft_override overrides[] = {
        {"token_embd.weight", ggml_backend_dev_buffer_type(devices[0])}, {nullptr, nullptr}};
    mp.tensor_buft_overrides = overrides;
    auto model = llama_model_load_from_file(argv[1], mp);
    assert(model != nullptr);
    auto cp = llama_context_default_params();
    cp.n_ctx = static_cast<uint32_t>(((prompt.size() + forced.size() + 255) / 256) * 256);
    cp.n_batch = cp.n_ubatch = cp.n_ctx;
    cp.type_k = cp.type_v = GGML_TYPE_F32;
    cp.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_DISABLED;
    cp.n_threads = cp.n_threads_batch = 4;
    auto ctx = llama_init_from_model(model, cp);
    assert(ctx != nullptr);
    int vocabulary = llama_vocab_n_tokens(llama_model_get_vocab(model));
    for (auto token : prompt) { assert(token < vocabulary); }
    for (auto token : forced) { assert(token < vocabulary); }
    assert(llama_decode(ctx, llama_batch_get_one(prompt.data(), prompt.size())) == 0);
    auto output = std::fopen(argv[5], "wb");
    assert(output != nullptr);
    for (size_t step = 0;; ++step) {
        auto logits = llama_get_logits_ith(ctx, -1);
        assert(logits != nullptr);
        int best = 0;
        for (int i = 1; i < vocabulary; ++i) { if (logits[i] > logits[best]) { best = i; } }
        std::printf("step=%zu argmax=%d vocabulary=%d\n", step, best, vocabulary);
        assert(std::fwrite(logits, sizeof(float), vocabulary, output) == size_t(vocabulary));
        if (step == forced.size()) { break; }
        assert(llama_decode(ctx, llama_batch_get_one(&forced[step], 1)) == 0);
    }
    assert(std::fclose(output) == 0);
    llama_free(ctx);
    llama_model_free(model);
    llama_backend_free();
}
