#include "native_cuda_q40_ffn.h"

#include <cuda_fp16.h>
#include <cuda_runtime.h>

#include <new>
#include <stdint.h>

namespace {
constexpr int WIDTH = 2048;
constexpr int HIDDEN = 6144;
constexpr int THREADS = 128;
constexpr int ROWS_PER_BLOCK = 2;
constexpr int WARPS_PER_ROW = 2;
constexpr int LANES_PER_ROW = 32 * WARPS_PER_ROW;
constexpr int DOWN_ROWS_PER_BLOCK = 1;
constexpr int DOWN_WARPS_PER_ROW = 4;
constexpr int DOWN_LANES_PER_ROW = 32 * DOWN_WARPS_PER_ROW;
constexpr int Q40_BLOCK = 32;
constexpr int WEIGHT_BLOCKS = WIDTH * HIDDEN / Q40_BLOCK;

#if defined(ALIGN_CUDA_Q4_TESTING)
int failure_operation = 0;
bool injected(int operation) {
    if (failure_operation != operation) return false;
    failure_operation = 0;
    return true;
}
#else
bool injected(int) { return false; }
#endif

struct Q40Block {
    __half scale;
    // The 18-byte block stride guarantees two-byte, not four-byte, alignment.
    uint16_t packed[8];
};
static_assert(sizeof(Q40Block) == 18, "Q4_0 block layout changed");
static_assert(alignof(Q40Block) == 2, "Q4_0 packed loads require two-byte alignment");
static_assert(offsetof(Q40Block, packed) == 2, "Q4_0 packed payload offset changed");
struct Q81Block {
    __half2 scale_sum;
    int8_t values[32];
};
static_assert(sizeof(Q81Block) == 36, "Q8_1 block layout changed");

struct Context {
    bool split = false;
    bool ready = false;
    bool poisoned = false;
    cudaStream_t stream = nullptr;
    cudaGraph_t graph = nullptr;
    cudaGraphExec_t executable = nullptr;
    float *gated = nullptr;
    float *output = nullptr;
    Q81Block *qinput = nullptr;
    Q81Block *qgated = nullptr;
    const void *gate = nullptr;
    const void *up = nullptr;
    const void *down = nullptr;
    const float *input = nullptr;
};

__global__ void quantize_q81(const float *input, Q81Block *output) {
    const int block = blockIdx.x;
    const int lane = threadIdx.x;
    const float value = input[block * Q40_BLOCK + lane];
    float maximum = fabsf(value);
    float sum = value;
    for (int step = 16; step > 0; step >>= 1) {
        maximum = fmaxf(maximum, __shfl_down_sync(0xffffffff, maximum, step));
        sum += __shfl_down_sync(0xffffffff, sum, step);
    }
    const float scale = __shfl_sync(0xffffffff, maximum / 127.0f, 0);
    output[block].values[lane] = scale == 0.0f ? 0 : int8_t(roundf(value / scale));
    if (lane == 0) output[block].scale_sum = __floats2half2_rn(scale, sum);
}

template<bool Split>
__device__ float dot_full(const void *weights, int index, const Q81Block &input) {
    const auto *raw = static_cast<const Q40Block *>(weights);
    uint4 payload{};
    if constexpr (Split) payload = static_cast<const uint4 *>(weights)[index];
    const uint32_t words[4] = {payload.x, payload.y, payload.z, payload.w};
    int sum = 0;
#pragma unroll
    for (int j = 0; j < 4; ++j) {
        uint32_t packed;
        if constexpr (Split) packed = words[j];
        else packed = uint32_t(raw[index].packed[j * 2])
            | (uint32_t(raw[index].packed[j * 2 + 1]) << 16);
        const int low = int(packed & 0x0f0f0f0fU);
        const int high = int((packed >> 4) & 0x0f0f0f0fU);
        const int qlow = int(reinterpret_cast<const uint32_t *>(input.values)[j]);
        const int qhigh = int(reinterpret_cast<const uint32_t *>(input.values + 16)[j]);
        sum = __dp4a(low, qlow, sum);
        sum = __dp4a(high, qhigh, sum);
    }
    const float2 scale_sum = __half22float2(input.scale_sum);
    const __half scale = Split
        ? reinterpret_cast<const __half *>(static_cast<const uint8_t *>(weights)
            + 16 * WEIGHT_BLOCKS)[index] : raw[index].scale;
    return __half2float(scale) * (float(sum) * scale_sum.x - 8.0f * scale_sum.y);
}

// Neighboring lanes consume the two halves of one packed Q4_0 block.
template<bool Split>
__device__ float dot_half(const void *weights, int index, const Q81Block &input, int half) {
    const auto *raw = static_cast<const Q40Block *>(weights);
    uint2 payload{};
    if constexpr (Split) payload = static_cast<const uint2 *>(weights)[2 * index + half];
    const uint32_t words[2] = {payload.x, payload.y};
    int sum = 0;
#pragma unroll
    for (int j = 0; j < 2; ++j) {
        const int offset = half * 4 + j * 2;
        uint32_t packed;
        if constexpr (Split) packed = words[j];
        else packed = uint32_t(raw[index].packed[offset])
            | (uint32_t(raw[index].packed[offset + 1]) << 16);
        const int low = int(packed & 0x0f0f0f0fU);
        const int high = int((packed >> 4) & 0x0f0f0f0fU);
        const int qlow = int(reinterpret_cast<const uint32_t *>(input.values + half * 8)[j]);
        const int qhigh = int(reinterpret_cast<const uint32_t *>(input.values + 16 + half * 8)[j]);
        sum = __dp4a(low, qlow, sum);
        sum = __dp4a(high, qhigh, sum);
    }
    const float2 scale_sum = __half22float2(input.scale_sum);
    const __half scale = Split
        ? reinterpret_cast<const __half *>(static_cast<const uint8_t *>(weights)
            + 16 * WEIGHT_BLOCKS)[index] : raw[index].scale;
    return __half2float(scale) * (float(sum) * scale_sum.x - 4.0f * scale_sum.y);
}

__device__ float reduce(float value) {
    for (int width = 16; width > 0; width >>= 1) {
        value += __shfl_down_sync(0xffffffff, value, width);
    }
    return value;
}

template<bool Split>
__global__ void gate_up_swiglu(const void *gate, const void *up,
        const Q81Block *input, float *gated) {
    const int lane = threadIdx.x % LANES_PER_ROW;
    const int local_row = threadIdx.x / LANES_PER_ROW;
    const int row = blockIdx.x * ROWS_PER_BLOCK + local_row;
    __shared__ float gate_partial[ROWS_PER_BLOCK][WARPS_PER_ROW];
    __shared__ float up_partial[ROWS_PER_BLOCK][WARPS_PER_ROW];
    float gate_sum = 0.0f;
    float up_sum = 0.0f;
    for (int block = lane; block < WIDTH / Q40_BLOCK; block += LANES_PER_ROW) {
        const int weight = row * (WIDTH / Q40_BLOCK) + block;
        gate_sum += dot_full<Split>(gate, weight, input[block]);
        up_sum += dot_full<Split>(up, weight, input[block]);
    }
    gate_sum = reduce(gate_sum);
    up_sum = reduce(up_sum);
    if ((threadIdx.x & 31) == 0) {
        gate_partial[local_row][lane >> 5] = gate_sum;
        up_partial[local_row][lane >> 5] = up_sum;
    }
    __syncthreads();
    if (lane == 0) {
        gate_sum = gate_partial[local_row][0] + gate_partial[local_row][1];
        up_sum = up_partial[local_row][0] + up_partial[local_row][1];
        gated[row] = (gate_sum / (1.0f + __expf(-gate_sum))) * up_sum;
    }
}

template<bool Split>
__global__ void down_matvec(const void *weight, const Q81Block *input, float *output) {
    const int lane = threadIdx.x % DOWN_LANES_PER_ROW;
    const int local_row = threadIdx.x / DOWN_LANES_PER_ROW;
    const int row = blockIdx.x * DOWN_ROWS_PER_BLOCK + local_row;
    __shared__ float partial[DOWN_ROWS_PER_BLOCK][DOWN_WARPS_PER_ROW];
    float sum = 0.0f;
    for (int piece = lane; piece < 2 * HIDDEN / Q40_BLOCK; piece += DOWN_LANES_PER_ROW) {
        const int block = piece / 2;
        sum += dot_half<Split>(weight, row * (HIDDEN / Q40_BLOCK) + block,
            input[block], piece & 1);
    }
    sum = reduce(sum);
    if ((threadIdx.x & 31) == 0) partial[local_row][lane >> 5] = sum;
    __syncthreads();
    if (lane == 0) output[row] = partial[local_row][0] + partial[local_row][1]
        + partial[local_row][2] + partial[local_row][3];
}

bool failed(Context *ctx) {
    ctx->ready = false;
    ctx->poisoned = true;
    return false;
}

bool complete(Context *ctx) {
    if (injected(9) || cudaGraphLaunch(ctx->executable, ctx->stream) != cudaSuccess)
        return failed(ctx);
    // A forced completion failure leaves work outstanding; close must drain it.
    if (injected(10) || cudaStreamSynchronize(ctx->stream) != cudaSuccess)
        return failed(ctx);
    ctx->ready = true;
    return true;
}
}

extern "C" void *align_native_cuda_q40_ffn_open(int width, int hidden) {
    return align_native_cuda_q40_ffn_open_layout(width, hidden, 0);
}

extern "C" void *align_native_cuda_q40_ffn_open_layout(int width, int hidden, int layout) {
    if (width != WIDTH || hidden != HIDDEN || (layout != 0 && layout != 1)) return nullptr;
    Context *ctx = new (std::nothrow) Context;
    if (ctx == nullptr) return nullptr;
    ctx->split = layout == 1;
    if (injected(1) || cudaStreamCreateWithFlags(&ctx->stream, cudaStreamNonBlocking) != cudaSuccess
        || injected(2) || cudaMalloc(&ctx->gated, HIDDEN * sizeof(float)) != cudaSuccess
        || injected(3) || cudaMalloc(&ctx->output, WIDTH * sizeof(float)) != cudaSuccess
        || injected(4) || cudaMalloc(&ctx->qinput, WIDTH / Q40_BLOCK * sizeof(Q81Block)) != cudaSuccess
        || injected(5) || cudaMalloc(&ctx->qgated, HIDDEN / Q40_BLOCK * sizeof(Q81Block)) != cudaSuccess) {
        align_native_cuda_q40_ffn_close(ctx);
        return nullptr;
    }
    return ctx;
}

extern "C" int align_native_cuda_q40_ffn_run(void *context, const void *gate, const void *up,
        const void *down, const float *input) {
    auto *ctx = static_cast<Context *>(context);
    if (ctx == nullptr) return 0;
    ctx->ready = false;
    if (ctx->poisoned || gate == nullptr || up == nullptr || down == nullptr || input == nullptr)
        return 0;
    if (ctx->executable != nullptr) {
        if (ctx->gate != gate || ctx->up != up || ctx->down != down || ctx->input != input)
            return 0;
        return complete(ctx);
    }
    if (injected(6) || cudaStreamBeginCapture(ctx->stream, cudaStreamCaptureModeThreadLocal) != cudaSuccess)
        return failed(ctx);
    quantize_q81<<<WIDTH / Q40_BLOCK, Q40_BLOCK, 0, ctx->stream>>>(input, ctx->qinput);
    bool launched = cudaGetLastError() == cudaSuccess;
    if (ctx->split) gate_up_swiglu<true><<<HIDDEN / ROWS_PER_BLOCK, THREADS, 0, ctx->stream>>>(
        gate, up, ctx->qinput, ctx->gated);
    else gate_up_swiglu<false><<<HIDDEN / ROWS_PER_BLOCK, THREADS, 0, ctx->stream>>>(
        gate, up, ctx->qinput, ctx->gated);
    launched = cudaGetLastError() == cudaSuccess && launched;
    quantize_q81<<<HIDDEN / Q40_BLOCK, Q40_BLOCK, 0, ctx->stream>>>(
        ctx->gated, ctx->qgated);
    launched = cudaGetLastError() == cudaSuccess && launched;
    if (ctx->split) down_matvec<true><<<WIDTH / DOWN_ROWS_PER_BLOCK, THREADS, 0, ctx->stream>>>(
        down, ctx->qgated, ctx->output);
    else down_matvec<false><<<WIDTH / DOWN_ROWS_PER_BLOCK, THREADS, 0, ctx->stream>>>(
        down, ctx->qgated, ctx->output);
    launched = cudaGetLastError() == cudaSuccess && launched;
    const cudaError_t captured = cudaStreamEndCapture(ctx->stream, &ctx->graph);
    if (injected(7) || captured != cudaSuccess || !launched || injected(8)
        || cudaGraphInstantiate(&ctx->executable, ctx->graph, 0) != cudaSuccess)
        return failed(ctx);
    ctx->gate = gate;
    ctx->up = up;
    ctx->down = down;
    ctx->input = input;
    return complete(ctx);
}

extern "C" int align_native_cuda_q40_ffn_read(void *context, float *gated,
        size_t gated_count, float *output, size_t output_count) {
    auto *ctx = static_cast<Context *>(context);
    if (ctx == nullptr || !ctx->ready || ctx->poisoned || gated == nullptr || output == nullptr
        || gated_count != HIDDEN || output_count != WIDTH) return 0;
    if (injected(11) || cudaMemcpy(gated, ctx->gated, HIDDEN * sizeof(float), cudaMemcpyDeviceToHost)
            != cudaSuccess || injected(12)
        || cudaMemcpy(output, ctx->output, WIDTH * sizeof(float), cudaMemcpyDeviceToHost)
            != cudaSuccess) return failed(ctx);
    return 1;
}

extern "C" void align_native_cuda_q40_ffn_close(void *context) {
    auto *ctx = static_cast<Context *>(context);
    if (ctx == nullptr) return;
    if (ctx->stream != nullptr) cudaStreamSynchronize(ctx->stream);
    if (ctx->executable != nullptr) cudaGraphExecDestroy(ctx->executable);
    if (ctx->graph != nullptr) cudaGraphDestroy(ctx->graph);
    if (ctx->qgated != nullptr) cudaFree(ctx->qgated);
    if (ctx->qinput != nullptr) cudaFree(ctx->qinput);
    if (ctx->output != nullptr) cudaFree(ctx->output);
    if (ctx->gated != nullptr) cudaFree(ctx->gated);
    if (ctx->stream != nullptr) cudaStreamDestroy(ctx->stream);
    delete ctx;
}

#if defined(ALIGN_CUDA_Q4_TESTING)
extern "C" void align_native_cuda_q40_ffn_test_fail(int operation) {
    failure_operation = operation;
}
#endif
