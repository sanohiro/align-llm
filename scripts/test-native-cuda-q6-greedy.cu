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

static void check(Context *ctx, const std::vector<float> &values, bool prefetched = false) {
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
    ctx->choice_ready = false;
    if (prefetched) {
        require(enqueue_choice(ctx) && cudaStreamSynchronize(ctx->stream) == cudaSuccess,
            "prefetched fixture selection failed");
        ctx->choice_ready = true;
    }
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
    if (!prefetched) check(ctx, values, true);
}

static void check_tail(Context *ctx, Q6Block *weights, float *input) {
    require(align_native_cuda_q6_tail_enable(ctx) == 1
        && align_native_cuda_q6_tail_enable(ctx) == 0, "tail allocation/reselection failed");
    float *attention = nullptr, *norm = nullptr;
    void *q4 = nullptr;
    const size_t q4_bytes = 7077888;
    require(cudaMalloc(&attention, WIDTH * sizeof(float)) == cudaSuccess
        && cudaMalloc(&norm, WIDTH * sizeof(float)) == cudaSuccess
        && cudaMalloc(&q4, q4_bytes) == cudaSuccess, "tail fixture allocation failed");
    std::vector<float> x(WIDTH), a(WIDTH), w(WIDTH), actual(WIDTH), residual(WIDTH);
    double squares = 0.0;
    for (int index = 0; index < WIDTH; ++index) {
        x[index] = float(index % 97 - 48) / 8.0f;
        a[index] = float(index % 31 - 15) / 16.0f;
        w[index] = float(index % 19 - 9) / 7.0f;
        const float value = x[index] + a[index];
        squares += double(value) * value;
    }
    const float epsilon = 1e-6f;
    require(cudaMemcpy(input, x.data(), WIDTH * sizeof(float), cudaMemcpyHostToDevice) == cudaSuccess
        && cudaMemcpy(attention, a.data(), WIDTH * sizeof(float), cudaMemcpyHostToDevice) == cudaSuccess
        && cudaMemcpy(norm, w.data(), WIDTH * sizeof(float), cudaMemcpyHostToDevice) == cudaSuccess
        && cudaMemset(q4, 0, q4_bytes) == cudaSuccess, "tail fixture upload failed");
    residual_norm<<<1, 256, 0, ctx->stream>>>(input, attention, norm, epsilon,
        ctx->normalized, ctx->residual);
    require(cudaGetLastError() == cudaSuccess && cudaStreamSynchronize(ctx->stream) == cudaSuccess
        && cudaMemcpy(actual.data(), ctx->normalized, WIDTH * sizeof(float), cudaMemcpyDeviceToHost)
            == cudaSuccess
        && cudaMemcpy(residual.data(), ctx->residual, WIDTH * sizeof(float), cudaMemcpyDeviceToHost)
            == cudaSuccess, "residual/norm fixture failed");
    const double inverse = 1.0 / std::sqrt(squares / WIDTH + epsilon);
    for (int index = 0; index < WIDTH; ++index) {
        const float value = x[index] + a[index];
        require(residual[index] == value, "residual arithmetic changed");
        require(std::abs(double(actual[index]) - double(value) * inverse * w[index]) < 2e-6,
            "learned RMS normalization exceeded scalar reference bound");
    }
    int64_t token = -1;
    for (int kind = 0; kind < 3; ++kind) {
        for (int replay = 0; replay < 3; ++replay) {
            require(align_native_cuda_q6_tail_run(ctx, kind, weights, input, attention,
                    norm, q4, q4, q4, norm, epsilon) == 1
                && align_native_cuda_q6_head_greedy(ctx, &token) == 1 && token == 0,
                "captured/replayed tail changed zero-weight greedy choice");
            require(cudaMemcpy(actual.data(), ctx->normalized, WIDTH * sizeof(float),
                cudaMemcpyDeviceToHost) == cudaSuccess, "tail normalized output read failed");
            for (int index = 0; index < WIDTH; ++index)
                require(std::abs(double(actual[index]) - double(x[index] + a[index]) * inverse
                    * w[index]) < 2e-6, "connected tail lost FFN residual or head norm");
        }
        require(align_native_cuda_q6_tail_run(ctx, kind, weights, attention, input,
                norm, q4, q4, q4, norm, epsilon) == 0
            && align_native_cuda_q6_head_greedy(ctx, &token) == 0 && token == -1,
            "changed captured pointer accepted or stale choice retained");
        require(align_native_cuda_q6_tail_run(ctx, kind, weights, input, attention,
            norm, q4, q4, q4, norm, 2 * epsilon) == 0, "changed epsilon accepted");
    }
    require(align_native_cuda_q6_tail_reset(ctx, -1) == 1
        && align_native_cuda_q6_head_greedy(ctx, &token) == 0 && token == -1,
        "all-kind reset left readable output");
    require(align_native_cuda_q6_tail_run(ctx, 1, weights, attention, input, norm,
            q4, q4, q4, norm, 2 * epsilon) == 1
        && align_native_cuda_q6_head_greedy(ctx, &token) == 1 && token == 0,
        "reset refused valid replacement graph");
    for (float bad : {0.0f, -epsilon, std::numeric_limits<float>::quiet_NaN(),
                     std::numeric_limits<float>::infinity()})
        require(align_native_cuda_q6_tail_run(ctx, 0, weights, input, attention,
            norm, q4, q4, q4, norm, bad) == 0, "invalid epsilon accepted");
    require(align_native_cuda_q6_tail_run(ctx, 3, weights, input, attention, norm,
            q4, q4, q4, norm, epsilon) == 0
        && align_native_cuda_q6_tail_run(ctx, 0, weights, nullptr, attention, norm,
            q4, q4, q4, norm, epsilon) == 0
        && align_native_cuda_q6_tail_reset(ctx, 3) == 0
        && align_native_cuda_q6_tail_reset(ctx, -1) == 1, "invalid tail input accepted");
    require(cudaFree(q4) == cudaSuccess && cudaFree(norm) == cudaSuccess
        && cudaFree(attention) == cudaSuccess, "tail borrowed fixture release failed");
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
        Q6Block *weights = nullptr;
        float *input = nullptr;
        const size_t weight_bytes = size_t(ROWS) * (WIDTH / 256) * sizeof(Q6Block);
        require(cudaMalloc(&weights, weight_bytes) == cudaSuccess
            && cudaMalloc(&input, WIDTH * sizeof(float)) == cudaSuccess,
            "projection fixture allocation failed");
        require(cudaMemsetAsync(weights, 0, weight_bytes, ctx->stream) == cudaSuccess
            && cudaMemsetAsync(input, 0, WIDTH * sizeof(float), ctx->stream) == cudaSuccess
            && cudaStreamSynchronize(ctx->stream) == cudaSuccess,
            "projection fixture initialization failed");
        require(align_native_cuda_q6_head_run_greedy(ctx, weights, input) == 1
            && align_native_cuda_q6_head_greedy(ctx, &token) == 1 && token == 0,
            "prefetched projection changed all-zero first-index choice");
        require(align_native_cuda_q6_head_run_greedy(ctx, nullptr, nullptr) == 0
            && align_native_cuda_q6_head_greedy(ctx, &token) == 0 && token == -1,
            "failed prefetched projection retained stale choice");
        check_tail(ctx, weights, input);
        require(cudaFree(input) == cudaSuccess && cudaFree(weights) == cudaSuccess,
            "projection fixture release failed");
        align_native_cuda_q6_head_close(ctx);
    }
    align_native_cuda_q6_head_close(nullptr);
    puts("CUDA native-head greedy: ties, signed zero, extreme/random finite rows, "
         "nonfinite rejection, repeated/stale reads, connected tail scalar norm/residual, "
         "capture/replay/identity/reset and construction pass");
}
