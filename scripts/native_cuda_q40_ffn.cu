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

__device__ float dot_full(const Q40Block &block, const Q81Block &input) {
    int sum = 0;
#pragma unroll
    for (int j = 0; j < 4; ++j) {
        const uint32_t packed = uint32_t(block.packed[j * 2])
            | (uint32_t(block.packed[j * 2 + 1]) << 16);
        const int low = int(packed & 0x0f0f0f0fU);
        const int high = int((packed >> 4) & 0x0f0f0f0fU);
        const int qlow = int(reinterpret_cast<const uint32_t *>(input.values)[j]);
        const int qhigh = int(reinterpret_cast<const uint32_t *>(input.values + 16)[j]);
        sum = __dp4a(low, qlow, sum);
        sum = __dp4a(high, qhigh, sum);
    }
    const float2 scale_sum = __half22float2(input.scale_sum);
    return __half2float(block.scale) * (float(sum) * scale_sum.x - 8.0f * scale_sum.y);
}

// Neighboring lanes consume the two halves of one packed Q4_0 block.
__device__ float dot_half(const Q40Block &block, const Q81Block &input, int half) {
    int sum = 0;
#pragma unroll
    for (int j = 0; j < 2; ++j) {
        const int offset = half * 4 + j * 2;
        const uint32_t packed = uint32_t(block.packed[offset])
            | (uint32_t(block.packed[offset + 1]) << 16);
        const int low = int(packed & 0x0f0f0f0fU);
        const int high = int((packed >> 4) & 0x0f0f0f0fU);
        const int qlow = int(reinterpret_cast<const uint32_t *>(input.values + half * 8)[j]);
        const int qhigh = int(reinterpret_cast<const uint32_t *>(input.values + 16 + half * 8)[j]);
        sum = __dp4a(low, qlow, sum);
        sum = __dp4a(high, qhigh, sum);
    }
    const float2 scale_sum = __half22float2(input.scale_sum);
    return __half2float(block.scale) * (float(sum) * scale_sum.x - 4.0f * scale_sum.y);
}

__device__ float reduce(float value) {
    for (int width = 16; width > 0; width >>= 1) {
        value += __shfl_down_sync(0xffffffff, value, width);
    }
    return value;
}

__global__ void gate_up_swiglu(const Q40Block *gate, const Q40Block *up,
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
        gate_sum += dot_full(gate[weight], input[block]);
        up_sum += dot_full(up[weight], input[block]);
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

__global__ void down_matvec(const Q40Block *weight, const Q81Block *input, float *output) {
    const int lane = threadIdx.x % DOWN_LANES_PER_ROW;
    const int local_row = threadIdx.x / DOWN_LANES_PER_ROW;
    const int row = blockIdx.x * DOWN_ROWS_PER_BLOCK + local_row;
    __shared__ float partial[DOWN_ROWS_PER_BLOCK][DOWN_WARPS_PER_ROW];
    float sum = 0.0f;
    for (int piece = lane; piece < 2 * HIDDEN / Q40_BLOCK; piece += DOWN_LANES_PER_ROW) {
        const int block = piece / 2;
        sum += dot_half(weight[row * (HIDDEN / Q40_BLOCK) + block], input[block], piece & 1);
    }
    sum = reduce(sum);
    if ((threadIdx.x & 31) == 0) partial[local_row][lane >> 5] = sum;
    __syncthreads();
    if (lane == 0) output[row] = partial[local_row][0] + partial[local_row][1]
        + partial[local_row][2] + partial[local_row][3];
}
}

extern "C" void *align_native_cuda_q40_ffn_open(int width, int hidden) {
    if (width != WIDTH || hidden != HIDDEN) return nullptr;
    Context *ctx = new (std::nothrow) Context;
    if (ctx == nullptr) return nullptr;
    if (cudaStreamCreateWithFlags(&ctx->stream, cudaStreamNonBlocking) != cudaSuccess
        || cudaMalloc(&ctx->gated, HIDDEN * sizeof(float)) != cudaSuccess
        || cudaMalloc(&ctx->output, WIDTH * sizeof(float)) != cudaSuccess
        || cudaMalloc(&ctx->qinput, WIDTH / Q40_BLOCK * sizeof(Q81Block)) != cudaSuccess
        || cudaMalloc(&ctx->qgated, HIDDEN / Q40_BLOCK * sizeof(Q81Block)) != cudaSuccess) {
        align_native_cuda_q40_ffn_close(ctx);
        return nullptr;
    }
    return ctx;
}

extern "C" int align_native_cuda_q40_ffn_run(void *context, const void *gate, const void *up,
        const void *down, const float *input) {
    auto *ctx = static_cast<Context *>(context);
    if (ctx == nullptr || gate == nullptr || up == nullptr || down == nullptr || input == nullptr)
        return 0;
    if (ctx->executable != nullptr) {
        if (ctx->gate != gate || ctx->up != up || ctx->down != down || ctx->input != input)
            return 0;
        return cudaGraphLaunch(ctx->executable, ctx->stream) == cudaSuccess
            && cudaStreamSynchronize(ctx->stream) == cudaSuccess;
    }
    if (cudaStreamBeginCapture(ctx->stream, cudaStreamCaptureModeThreadLocal) != cudaSuccess)
        return 0;
    quantize_q81<<<WIDTH / Q40_BLOCK, Q40_BLOCK, 0, ctx->stream>>>(input, ctx->qinput);
    bool launched = cudaGetLastError() == cudaSuccess;
    gate_up_swiglu<<<HIDDEN / ROWS_PER_BLOCK, THREADS, 0, ctx->stream>>>(
        static_cast<const Q40Block *>(gate), static_cast<const Q40Block *>(up),
        ctx->qinput, ctx->gated);
    launched = cudaGetLastError() == cudaSuccess && launched;
    quantize_q81<<<HIDDEN / Q40_BLOCK, Q40_BLOCK, 0, ctx->stream>>>(
        ctx->gated, ctx->qgated);
    launched = cudaGetLastError() == cudaSuccess && launched;
    down_matvec<<<WIDTH / DOWN_ROWS_PER_BLOCK, THREADS, 0, ctx->stream>>>(
        static_cast<const Q40Block *>(down), ctx->qgated, ctx->output);
    launched = cudaGetLastError() == cudaSuccess && launched;
    if (cudaStreamEndCapture(ctx->stream, &ctx->graph) != cudaSuccess || !launched
        || cudaGraphInstantiate(&ctx->executable, ctx->graph, 0) != cudaSuccess)
        return 0;
    ctx->gate = gate;
    ctx->up = up;
    ctx->down = down;
    ctx->input = input;
    return cudaGraphLaunch(ctx->executable, ctx->stream) == cudaSuccess
        && cudaStreamSynchronize(ctx->stream) == cudaSuccess;
}

extern "C" int align_native_cuda_q40_ffn_read(void *context, float *gated,
        size_t gated_count, float *output, size_t output_count) {
    auto *ctx = static_cast<Context *>(context);
    if (ctx == nullptr || gated == nullptr || output == nullptr
        || gated_count != HIDDEN || output_count != WIDTH) return 0;
    return cudaMemcpy(gated, ctx->gated, HIDDEN * sizeof(float), cudaMemcpyDeviceToHost)
               == cudaSuccess
        && cudaMemcpy(output, ctx->output, WIDTH * sizeof(float), cudaMemcpyDeviceToHost)
               == cudaSuccess;
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
