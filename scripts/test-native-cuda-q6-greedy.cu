// Exercise the checked-in reducer with adversarial logits, without model arithmetic.
#include "native_cuda_q6_head.cu"
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <random>
#include <vector>

static void require(bool condition, const char *message) {
    if (!condition) { fprintf(stderr, "%s\n", message); std::exit(1); }
}

static void check(Context *ctx, const std::vector<float> &values) {
    int expected = 0;
    bool finite = true;
    for (int index = 0; index < ROWS; ++index) {
        finite = finite && std::isfinite(values[index]);
        if (values[index] > values[expected]) expected = index;
    }
    require(cudaMemcpyAsync(ctx->output, values.data(), ROWS * sizeof(float),
        cudaMemcpyHostToDevice, ctx->stream) == cudaSuccess
        && cudaStreamSynchronize(ctx->stream) == cudaSuccess, "fixture upload failed");
    ctx->ready = true;  // Test-only injection into the exact helper's private output.
    int64_t token = 99;
    const int status = align_native_cuda_q6_head_greedy(ctx, &token);
    if (!(finite ? status == 1 && token == expected : status == 0 && token == -1))
        fprintf(stderr, "expected finite=%d token=%d; status=%d token=%lld\n",
            int(finite), expected, status, static_cast<long long>(token));
    require(finite ? status == 1 && token == expected : status == 0 && token == -1,
        "finite/first-index/nonfinite contract failed");
    if (finite) {
        require(align_native_cuda_q6_head_greedy(ctx, &token) == 1 && token == expected,
            "repeated read changed choice");
    } else {
        token = 99;
        require(align_native_cuda_q6_head_greedy(ctx, &token) == 0 && token == -1,
            "failed reduction left a readable stale token");
    }
}

int main() {
    int64_t token = 99;
    require(align_native_cuda_q6_head_greedy(nullptr, &token) == 0 && token == -1,
        "null context accepted");
    require(align_native_cuda_q6_head_open(-1) == nullptr, "invalid device accepted");
    for (int reuse = 0; reuse < 2; ++reuse) {
        auto *ctx = static_cast<Context *>(align_native_cuda_q6_head_open(0));
        require(ctx != nullptr, "context construction failed");
        require(align_native_cuda_q6_head_greedy(ctx, &token) == 0,
            "uninitialized output accepted");
        require(align_native_cuda_q6_head_greedy(ctx, nullptr) == 0,
            "null output pointer accepted");
        std::vector<float> values(ROWS, -1.0f);
        check(ctx, values);
        for (int first : {0, 31, 32, 255, 256, 8191, ROWS - 2}) {
            std::fill(values.begin(), values.end(), -1.0f);
            values[first] = 7.0f;
            values[ROWS - 1] = 7.0f;
            check(ctx, values);
        }
        std::fill(values.begin(), values.end(), -1.0f);
        values[31] = -0.0f;
        values[256] = 0.0f;
        check(ctx, values);
        std::fill(values.begin(), values.end(), -std::numeric_limits<float>::max());
        values[ROWS - 1] = std::numeric_limits<float>::max();
        check(ctx, values);
        std::mt19937 random(1234);
        for (int trial = 0; trial < 24; ++trial) {
            for (float &value : values) value = float(int(random() % 65536) - 32768);
            check(ctx, values);
        }
        for (float bad : {std::numeric_limits<float>::quiet_NaN(),
                          std::numeric_limits<float>::infinity(),
                          -std::numeric_limits<float>::infinity()}) {
            for (int index : {0, 31, 32, 255, 256, ROWS - 1}) {
                std::fill(values.begin(), values.end(), 1.0f);
                values[index] = bad;
                check(ctx, values);
            }
        }
        std::fill(values.begin(), values.end(), 1.0f);
        check(ctx, values);
        require(align_native_cuda_q6_head_run(ctx, nullptr, nullptr) == 0,
            "invalid projection accepted");
        token = 99;
        require(align_native_cuda_q6_head_greedy(ctx, &token) == 0 && token == -1,
            "failed projection left a readable stale token");
        align_native_cuda_q6_head_close(ctx);
    }
    align_native_cuda_q6_head_close(nullptr);
    puts("CUDA native-head greedy: ties, signed zero, extreme/random finite rows, "
         "nonfinite rejection, repeated/stale reads and construction pass");
}
