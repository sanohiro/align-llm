#include "llama.h"
#include "ggml-backend.h"

#include <cmath>
#include <chrono>
#include <cstdio>
#include <cstdlib>
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

static bool read_ids(const char * path, std::vector<llama_token> & ids) {
    std::ifstream input(path, std::ios::binary);
    if (!input) return false;
    const std::string json((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    const char * cursor = json.c_str();
    if (*cursor++ != '[') return false;
    while (*cursor != ']') {
        char * end = nullptr;
        const long value = std::strtol(cursor, &end, 10);
        if (end == cursor || value < 0 || value > 2147483647 || ids.size() >= 512) return false;
        ids.push_back(static_cast<llama_token>(value));
        cursor = end;
        if (*cursor == ',') ++cursor;
        else if (*cursor != ']') return false;
    }
    return !ids.empty() && cursor[1] == '\n' && cursor[2] == '\0';
}

int main(int argc, char ** argv) {
    const bool benchmark = (argc == 3 || argc == 4) && std::string(argv[2]) == "--decode-bench";
    const bool prefill = (argc == 4 || argc == 5) &&
        std::string(argv[2]) == "--prefill-128";
    const bool greedy = argc == 5 && std::string(argv[2]) == "--greedy-ids";
    if (argc != 4 && argc != 6 && !benchmark && !prefill && !greedy) {
        std::fprintf(stderr,
                     "usage: qwen35_llama_logits_oracle GGUF ALIGN_FIRST ALIGN_SECOND "
                     "[ALIGN_THIRD ALIGN_FOURTH] | GGUF --decode-bench [ALIGN_FINAL] "
                     "| GGUF --prefill-128 ALIGN_FINAL [ALIGN_DECODE] "
                     "| GGUF --greedy-ids PROMPT_IDS COUNT\n");
        return 2;
    }
    std::vector<llama_token> prompt;
    int32_t greedy_count = 0;
    if (greedy) {
        if (!read_ids(argv[3], prompt)) return 2;
        char * end = nullptr;
        const long parsed = std::strtol(argv[4], &end, 10);
        if (*end != '\0' || parsed < 1 || parsed > 128) return 2;
        greedy_count = static_cast<int32_t>(parsed);
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
    context_params.n_ctx = greedy ? 1024 : 512;
    context_params.n_batch = greedy ? 1024 : 512;
    context_params.n_ubatch = greedy ? 1024 : 512;
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
    if (passed && greedy) {
        passed = llama_decode(context, llama_batch_get_one(prompt.data(),
            static_cast<int32_t>(prompt.size()))) == 0;
        std::printf("[");
        for (int32_t step = 0; passed && step < greedy_count; ++step) {
            const float * logits = llama_get_logits(context);
            if (!logits || !std::isfinite(logits[0])) { passed = false; break; }
            int32_t top = 0;
            for (int32_t i = 1; i < vocab; ++i) {
                if (!std::isfinite(logits[i])) { passed = false; break; }
                if (logits[i] > logits[top]) top = i;
            }
            if (!passed) break;
            std::printf("%s%d", step == 0 ? "" : ",", top);
            if (step + 1 < greedy_count) {
                llama_token next = top;
                passed = llama_decode(context, llama_batch_get_one(&next, 1)) == 0;
            }
        }
        std::printf("]\n");
    }
    if (passed && prefill) {
        std::vector<llama_token> prompt(128, 0);
        prompt[1] = 23066;
        passed = llama_decode(context, llama_batch_get_one(prompt.data(), 128)) == 0;
        if (passed) {
            passed = llama_get_logits(context) != nullptr;
            llama_memory_clear(llama_get_memory(context), true);
        }
        const auto started = std::chrono::steady_clock::now();
        passed = passed && llama_decode(context, llama_batch_get_one(prompt.data(), 128)) == 0;
        const float * logits = passed ? llama_get_logits(context) : nullptr;
        const auto elapsed = std::chrono::steady_clock::now() - started;
        std::printf("{\"tokens\":128,\"elapsed_ns\":%lld}\n",
                    static_cast<long long>(
                        std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count()));
        passed = logits && compare(argv[3], logits, vocab, 127);
        if (passed && argc == 5) {
            llama_token next = 0;
            passed = llama_decode(context, llama_batch_get_one(&next, 1)) == 0;
            logits = passed ? llama_get_logits(context) : nullptr;
            passed = logits && compare(argv[4], logits, vocab, 128);
        }
    }
    for (int32_t step = 0; passed && !prefill && !greedy && step < (benchmark ? 4 : argc - 2); ++step) {
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
