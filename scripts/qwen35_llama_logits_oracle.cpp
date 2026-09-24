#include "llama.h"
#include "ggml-backend.h"

#include <cmath>
#include <chrono>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

static bool compare(const char * path, const float * reference, int32_t count,
                    int32_t step) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    if (!input || input.tellg() != static_cast<std::streamoff>(count * sizeof(float))) {
        std::fprintf(stderr, "step %d: missing or wrong-size Align logits\n", step);
        return false;
    }
    input.seekg(0);
    std::vector<float> actual(static_cast<size_t>(count));
    input.read(reinterpret_cast<char *>(actual.data()), count * sizeof(float));
    if (!input) {
        std::fprintf(stderr, "step %d: incomplete Align logits\n", step);
        return false;
    }
    double sum_abs = 0.0;
    double max_abs = 0.0;
    int32_t actual_top = 0;
    int32_t reference_top = 0;
    for (int32_t i = 0; i < count; ++i) {
        if (!std::isfinite(actual[i]) || !std::isfinite(reference[i])) {
            std::fprintf(stderr, "step %d: nonfinite logit at %d\n", step, i);
            return false;
        }
        const double difference = std::abs(static_cast<double>(actual[i]) - reference[i]);
        sum_abs += difference;
        if (difference > max_abs) max_abs = difference;
        if (actual[i] > actual[actual_top]) actual_top = i;
        if (reference[i] > reference[reference_top]) reference_top = i;
    }
    std::printf("step=%d count=%d max_abs=%.9g mean_abs=%.9g top_align=%d top_llama=%d\n",
                step, count, max_abs, sum_abs / count, actual_top, reference_top);
    return max_abs <= 0.01 && actual_top == reference_top;
}

int main(int argc, char ** argv) {
    const bool benchmark = (argc == 3 || argc == 4) && std::string(argv[2]) == "--decode-bench";
    if (argc != 4 && argc != 6 && !benchmark) {
        std::fprintf(stderr,
                     "usage: qwen35_llama_logits_oracle GGUF ALIGN_FIRST ALIGN_SECOND "
                     "[ALIGN_THIRD ALIGN_FOURTH] | GGUF --decode-bench [ALIGN_FINAL]\n");
        return 2;
    }
    llama_backend_init();
    if (!ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_GPU)) {
        std::fprintf(stderr, "pinned llama.cpp GPU backend is unavailable\n");
        return 3;
    }
    llama_model_params model_params = llama_model_default_params();
    model_params.n_gpu_layers = 99;
    llama_model * model = llama_model_load_from_file(argv[1], model_params);
    if (!model) return 3;
    llama_context_params context_params = llama_context_default_params();
    context_params.n_ctx = 512;
    context_params.n_batch = 512;
    context_params.n_ubatch = 512;
    context_params.n_threads = 4;
    context_params.n_threads_batch = 4;
    context_params.flash_attn_type = LLAMA_FLASH_ATTN_TYPE_ENABLED;
    llama_context * context = llama_init_from_model(model, context_params);
    if (!context) {
        llama_model_free(model);
        return 4;
    }
    const int32_t vocab = llama_vocab_n_tokens(llama_model_get_vocab(model));
    const llama_token tokens[4] = {0, 23066, 0, 0};
    bool passed = vocab == 248320;
    for (int32_t step = 0; passed && step < (benchmark ? 4 : argc - 2); ++step) {
        llama_token token = tokens[step];
        if (llama_decode(context, llama_batch_get_one(&token, 1)) != 0) {
            passed = false;
            break;
        }
        const float * logits = llama_get_logits(context);
        passed = logits && (benchmark || compare(argv[step + 2], logits, vocab, step));
    }
    if (passed && benchmark) {
        const auto started = std::chrono::steady_clock::now();
        for (int32_t step = 4; step < 128; ++step) {
            llama_token token = 0;
            if (llama_decode(context, llama_batch_get_one(&token, 1)) != 0) {
                passed = false;
                break;
            }
            const float * logits = llama_get_logits(context);
            if (!logits || !std::isfinite(logits[0])) {
                passed = false;
                break;
            }
        }
        const auto elapsed = std::chrono::steady_clock::now() - started;
        std::printf("{\"tokens\":124,\"elapsed_ns\":%lld}\n",
                    static_cast<long long>(
                        std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count()));
        if (passed && argc == 4) {
            passed = compare(argv[3], llama_get_logits(context), vocab, 127);
        }
    }
    llama_free(context);
    llama_model_free(model);
    return passed ? 0 : 5;
}
