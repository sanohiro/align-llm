// Thin CUDA kernel boundary for an Align-selected Q6_K output projection.
// Q6_K unpacking and Q8_1 conversion follow pinned ggml's formats and CUDA path.
// MIT License
// Copyright (c) 2023-2026 the ggml authors
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
#include "native_cuda_q6_head.h"
#include "native_cuda_q40_ffn.h"

#include <cuda_fp16.h>
#include <cuda_runtime.h>
#include <new>
#include <stdint.h>
#include <stdio.h>
#include <cmath>

namespace {
constexpr int WIDTH = 2048, ROWS = 248320;
constexpr int GREEDY_BLOCKS = (ROWS + 255) / 256;
struct Q6Block { uint8_t ql[128], qh[64]; int8_t scales[16]; __half d; };
struct Q8Block { int8_t q[32]; __half d, sum; };
struct Choice { float value; int index; };
static_assert(sizeof(Choice) == 8, "greedy result layout changed");
static_assert(sizeof(Q6Block) == 210, "Q6_K block layout changed");
static_assert(sizeof(Q8Block) == 36, "Q8_1 block layout changed");
static_assert(ROWS * sizeof(float) + WIDTH / 32 * sizeof(Q8Block)
              + (GREEDY_BLOCKS + 1) * sizeof(Choice)
              == ALIGN_NATIVE_CUDA_Q6_HEAD_DEVICE_BYTES,
              "native Q6_K allocation reservation changed");

struct TailGraph {
    cudaGraph_t graph = nullptr;
    cudaGraphExec_t executable = nullptr;
    const void *pointers[8]{};
    float epsilon = 0.0f;
};
static_assert(ALIGN_NATIVE_CUDA_Q40_FFN_DEVICE_BYTES + 2 * WIDTH * sizeof(float)
    == ALIGN_NATIVE_CUDA_FFN_TAIL_DEVICE_BYTES, "tail allocation reservation changed");

struct Context {
    cudaStream_t stream = nullptr;
    Q8Block *quantized = nullptr;
    float *output = nullptr;
    Choice *partials = nullptr, *choice = nullptr;
    int device = -1;
    bool ready = false;
    bool choice_ready = false;
    bool last_tail = false;
    Choice host_choice{0.0f, -1};
    void *ffn = nullptr;
    float *normalized = nullptr, *residual = nullptr;
    TailGraph tails[3];
};

// Both normalization boundaries retain the ordinary F32 residual and learned weight.
__global__ void residual_norm(const float *input, const float *attention,
        const float *weight, float epsilon, float *output, float *residual) {
    __shared__ float warps[8];
    float values[WIDTH / 256];
    float squares = 0.0f;
#pragma unroll
    for (int j = 0; j < WIDTH / 256; ++j) {
        const int index = threadIdx.x + j * 256;
        const float value = attention == nullptr ? input[index] : input[index] + attention[index];
        values[j] = value;
        squares += value * value;
        if (residual != nullptr) residual[index] = value;
    }
    for (int step = 16; step > 0; step >>= 1)
        squares += __shfl_down_sync(0xffffffff, squares, step);
    if ((threadIdx.x & 31) == 0) warps[threadIdx.x / 32] = squares;
    __syncthreads();
    if (threadIdx.x < 32) {
        squares = threadIdx.x < 8 ? warps[threadIdx.x] : 0.0f;
        for (int step = 16; step > 0; step >>= 1)
            squares += __shfl_down_sync(0xffffffff, squares, step);
        if (threadIdx.x == 0) warps[0] = rsqrtf(squares / float(WIDTH) + epsilon);
    }
    __syncthreads();
#pragma unroll
    for (int j = 0; j < WIDTH / 256; ++j) {
        const int index = threadIdx.x + j * 256;
        output[index] = (values[j] * warps[0]) * weight[index];
    }
}

__device__ Choice merge_choice(Choice left, Choice right) {
    if (left.index == -2 || right.index == -1) return left;
    if (right.index == -2 || left.index == -1 || right.value > left.value
        || (right.value == left.value && right.index < left.index)) return right;
    return left;
}

__device__ Choice reduce_choice(Choice current) {
    __shared__ Choice warps[8];
    const int lane = threadIdx.x & 31;
    for (int offset = 16; offset > 0; offset >>= 1) {
        Choice other{__shfl_down_sync(0xffffffff, current.value, offset),
                     __shfl_down_sync(0xffffffff, current.index, offset)};
        if (lane + offset < 32) current = merge_choice(current, other);
    }
    if (lane == 0) warps[threadIdx.x / 32] = current;
    __syncthreads();
    if (threadIdx.x < 32) {
        current = lane < 8 ? warps[lane] : Choice{0.0f, -1};
        for (int offset = 16; offset > 0; offset >>= 1) {
            Choice other{__shfl_down_sync(0xffffffff, current.value, offset),
                         __shfl_down_sync(0xffffffff, current.index, offset)};
            if (lane + offset < 32) current = merge_choice(current, other);
        }
    }
    return current;
}

__global__ void greedy_parts(const float *values, Choice *partials) {
    const int index = blockIdx.x * blockDim.x + threadIdx.x;
    const float value = index < ROWS ? values[index] : 0.0f;
    Choice current{value, index >= ROWS ? -1 : (isfinite(value) ? index : -2)};
    current = reduce_choice(current);
    if (threadIdx.x == 0) partials[blockIdx.x] = current;
}

__global__ void greedy_finish(const Choice *partials, Choice *result) {
    Choice current{0.0f, -1};
    for (int index = threadIdx.x; index < GREEDY_BLOCKS; index += blockDim.x)
        current = merge_choice(current, partials[index]);
    current = reduce_choice(current);
    if (threadIdx.x == 0) *result = current;
}

__global__ void quantize_input(const float *input, Q8Block *quantized) {
    const int lane = threadIdx.x & 31;
    const int block = (blockIdx.x * blockDim.x + threadIdx.x) / 32;
    const float x = input[block * 32 + lane];
    float maximum = fabsf(x);
    for (int offset = 16; offset > 0; offset >>= 1)
        maximum = fmaxf(maximum, __shfl_down_sync(0xffffffff, maximum, offset));
    maximum = __shfl_sync(0xffffffff, maximum, 0);
    const float d = maximum / 127.0f;
    quantized[block].q[lane] = maximum == 0.0f ? 0 : int8_t(roundf(x / d));
    if (lane == 0) quantized[block].d = __float2half(d);
}

__global__ void project(const Q6Block *weights, const Q8Block *input, float *output) {
    const int lane = threadIdx.x & 31;
    const int row = (blockIdx.x * blockDim.x + threadIdx.x) / 32;
    if (row >= ROWS) return;
    const int tid = lane / 2, ix = lane & 1;
    const int ip = tid / 8, l0 = 4 * (tid % 8), is = 8 * ip + l0 / 16;
    float acc = 0.0f;
    for (int block = ix; block < WIDTH / 256; block += 2) {
        const Q6Block &q = weights[row * (WIDTH / 256) + block];
        const float scale = __half2float(q.d);
        uint32_t packed[4] = {};
#pragma unroll
        for (int l = 0; l < 4; ++l) {
            const uint8_t q1 = q.ql[64 * ip + l0 + l];
            const uint8_t q2 = q.ql[64 * ip + l0 + 32 + l];
            const uint8_t high = q.qh[32 * ip + l0 + l];
            const int v0 = int((q1 & 15) | ((high & 3) << 4)) - 32;
            const int v1 = int((q2 & 15) | ((high & 12) << 2)) - 32;
            const int v2 = int((q1 >> 4) | (high & 48)) - 32;
            const int v3 = int((q2 >> 4) | ((high & 192) >> 2)) - 32;
            packed[0] |= uint32_t(uint8_t(v0)) << (8 * l);
            packed[1] |= uint32_t(uint8_t(v1)) << (8 * l);
            packed[2] |= uint32_t(uint8_t(v2)) << (8 * l);
            packed[3] |= uint32_t(uint8_t(v3)) << (8 * l);
        }
        const int group = block * 8 + ip * 4;
        const int p0 = __dp4a(int(packed[0]),
            *reinterpret_cast<const int *>(input[group + 0].q + l0), 0);
        const int p1 = __dp4a(int(packed[1]),
            *reinterpret_cast<const int *>(input[group + 1].q + l0), 0);
        const int p2 = __dp4a(int(packed[2]),
            *reinterpret_cast<const int *>(input[group + 2].q + l0), 0);
        const int p3 = __dp4a(int(packed[3]),
            *reinterpret_cast<const int *>(input[group + 3].q + l0), 0);
        float local = 0.0f;
        local += __half2float(input[group + 0].d) * float(p0 * q.scales[is]);
        local += __half2float(input[group + 1].d) * float(p1 * q.scales[is + 2]);
        local += __half2float(input[group + 2].d) * float(p2 * q.scales[is + 4]);
        local += __half2float(input[group + 3].d) * float(p3 * q.scales[is + 6]);
        acc += scale * local;
    }
    for (int offset = 16; offset > 0; offset >>= 1)
        acc += __shfl_down_sync(0xffffffff, acc, offset);
    if (lane == 0) output[row] = acc;
}

bool device_pointer(const void *pointer, int device) {
    cudaPointerAttributes attribute{};
    return pointer != nullptr && cudaPointerGetAttributes(&attribute, pointer) == cudaSuccess
        && attribute.type == cudaMemoryTypeDevice && attribute.device == device;
}

bool enqueue_choice(Context *ctx) {
    greedy_parts<<<GREEDY_BLOCKS, 256, 0, ctx->stream>>>(ctx->output, ctx->partials);
    if (cudaGetLastError() != cudaSuccess) return false;
    greedy_finish<<<1, 256, 0, ctx->stream>>>(ctx->partials, ctx->choice);
    if (cudaGetLastError() != cudaSuccess) return false;
    return cudaMemcpyAsync(&ctx->host_choice, ctx->choice, sizeof(Choice),
        cudaMemcpyDeviceToHost, ctx->stream) == cudaSuccess;
}
}  // namespace

extern "C" void *align_native_cuda_q6_head_open(int device_ordinal) {
    int count = 0;
    if (device_ordinal != 0 || cudaGetDeviceCount(&count) != cudaSuccess || count != 1
        || cudaSetDevice(device_ordinal) != cudaSuccess) return nullptr;
    auto *ctx = new (std::nothrow) Context;
    if (ctx == nullptr) return nullptr;
    ctx->device = device_ordinal;
    if (cudaStreamCreateWithFlags(&ctx->stream, cudaStreamNonBlocking) != cudaSuccess
        || cudaMalloc(&ctx->quantized, WIDTH / 32 * sizeof(Q8Block)) != cudaSuccess
        || cudaMalloc(&ctx->output, ROWS * sizeof(float)) != cudaSuccess
        || cudaMalloc(&ctx->partials, GREEDY_BLOCKS * sizeof(Choice)) != cudaSuccess
        || cudaMalloc(&ctx->choice, sizeof(Choice)) != cudaSuccess) {
        align_native_cuda_q6_head_close(ctx);
        return nullptr;
    }
    return ctx;
}

static int run_projection(void *opaque, const void *weight,
        const void *input, bool with_choice) {
    auto *ctx = static_cast<Context *>(opaque);
    if (ctx != nullptr) { ctx->ready = false; ctx->choice_ready = false; ctx->last_tail = false; }
    if (ctx == nullptr || ctx->stream == nullptr || ctx->quantized == nullptr
        || ctx->output == nullptr
        || cudaSetDevice(ctx->device) != cudaSuccess
        || !device_pointer(weight, ctx->device) || !device_pointer(input, ctx->device)) return 0;
#if defined(ALIGN_NATIVE_CUDA_Q6_FORCE_SUBMIT_FAILURE)
    if (ctx->ffn == nullptr) {
        fprintf(stderr, "native_q6_head forced submit failure\n");
        return 0;
    }
#endif
    quantize_input<<<WIDTH / 256, 256, 0, ctx->stream>>>(
        static_cast<const float *>(input), ctx->quantized);
    if (cudaGetLastError() != cudaSuccess) return 0;
    project<<<(ROWS + 7) / 8, 256, 0, ctx->stream>>>(
        static_cast<const Q6Block *>(weight), ctx->quantized, ctx->output);
    if (cudaGetLastError() != cudaSuccess) {
        cudaStreamSynchronize(ctx->stream);
        return 0;
    }
    const bool submitted = !with_choice || enqueue_choice(ctx);
    const cudaError_t completed = cudaStreamSynchronize(ctx->stream);
    if (!submitted || completed != cudaSuccess) return 0;
#if defined(ALIGN_NATIVE_CUDA_Q6_FORCE_COMPLETION_FAILURE)
    if (ctx->ffn == nullptr) {
        fprintf(stderr, "native_q6_head forced completion failure\n");
        return 0;
    }
#endif
    ctx->ready = true;
    ctx->choice_ready = with_choice;
    return 1;
}

extern "C" int align_native_cuda_q6_head_run(void *opaque, const void *weight,
        const void *input) {
    return run_projection(opaque, weight, input, false);
}

extern "C" int align_native_cuda_q6_head_run_greedy(void *opaque, const void *weight,
        const void *input) {
    return run_projection(opaque, weight, input, true);
}

extern "C" int align_native_cuda_q6_tail_enable(void *opaque) {
    auto *ctx = static_cast<Context *>(opaque);
    if (ctx == nullptr || ctx->ffn != nullptr || ctx->normalized != nullptr
        || ctx->residual != nullptr || cudaSetDevice(ctx->device) != cudaSuccess) return 0;
    if (cudaMalloc(&ctx->normalized, WIDTH * sizeof(float)) != cudaSuccess
        || cudaMalloc(&ctx->residual, WIDTH * sizeof(float)) != cudaSuccess
        || (ctx->ffn = align_native_cuda_q40_ffn_open(WIDTH, 6144)) == nullptr) {
        if (ctx->normalized != nullptr) cudaFree(ctx->normalized);
        if (ctx->residual != nullptr) cudaFree(ctx->residual);
        ctx->normalized = ctx->residual = nullptr;
        return 0;
    }
    return 1;
}

extern "C" int align_native_cuda_q6_tail_reset(void *opaque, int kind) {
    auto *ctx = static_cast<Context *>(opaque);
    if (ctx == nullptr || kind < -1 || kind >= 3) return 0;
    ctx->ready = ctx->choice_ready = false;
    ctx->last_tail = false;
    if (cudaSetDevice(ctx->device) != cudaSuccess
        || cudaStreamSynchronize(ctx->stream) != cudaSuccess) return 0;
    bool ok = true;
    for (int index = 0; index < 3; ++index) {
        if (kind != -1 && kind != index) continue;
        TailGraph &tail = ctx->tails[index];
        if (tail.executable != nullptr)
            ok = (cudaGraphExecDestroy(tail.executable) == cudaSuccess) && ok;
        if (tail.graph != nullptr) ok = (cudaGraphDestroy(tail.graph) == cudaSuccess) && ok;
        tail = TailGraph{};
    }
    return ok ? 1 : 0;
}

extern "C" int align_native_cuda_q6_tail_run(void *opaque, int kind, const void *weight,
        const float *input, const float *attention, const float *norm,
        const void *gate, const void *up, const void *down, const float *head_norm,
        float epsilon) {
    auto *ctx = static_cast<Context *>(opaque);
    if (ctx != nullptr) { ctx->ready = ctx->choice_ready = false; ctx->last_tail = true; }
    if (ctx == nullptr || kind < 0 || kind >= 3 || ctx->ffn == nullptr
        || ctx->normalized == nullptr || ctx->residual == nullptr
        || !std::isfinite(epsilon) || epsilon <= 0.0f
        || cudaSetDevice(ctx->device) != cudaSuccess) return 0;
    const void *pointers[] = {weight, input, attention, norm, gate, up, down, head_norm};
    TailGraph &tail = ctx->tails[kind];
    if (tail.executable != nullptr) {
        if (tail.epsilon != epsilon) return 0;
        for (int index = 0; index < 8; ++index)
            if (tail.pointers[index] != pointers[index]) return 0;
    } else {
        // Borrowed storage stays live until reset. Replay needs identity checks,
        // not eight repeated CUDA runtime attribute queries for the same pointers.
        for (const void *pointer : pointers) if (!device_pointer(pointer, ctx->device)) return 0;
    }
#if defined(ALIGN_NATIVE_CUDA_Q6_FORCE_SUBMIT_FAILURE)
    fprintf(stderr, "native_q6_head forced submit failure\n");
    fprintf(stderr, "native_ffn_tail forced submit failure\n");
    return 0;
#endif
    if (tail.executable == nullptr) {
        if (cudaStreamBeginCapture(ctx->stream, cudaStreamCaptureModeThreadLocal)
            != cudaSuccess) return 0;
        residual_norm<<<1, 256, 0, ctx->stream>>>(input, attention, norm, epsilon,
            ctx->normalized, ctx->residual);
        bool submitted = cudaGetLastError() == cudaSuccess;
        if (submitted) submitted = align_native_cuda_q40_ffn_enqueue(ctx->ffn,
            gate, up, down, ctx->normalized, ctx->residual, ctx->stream) == 1;
        if (submitted) {
            residual_norm<<<1, 256, 0, ctx->stream>>>(
                align_native_cuda_q40_ffn_output(ctx->ffn), nullptr, head_norm,
                epsilon, ctx->normalized, nullptr);
            submitted = cudaGetLastError() == cudaSuccess;
        }
        if (submitted) {
            quantize_input<<<WIDTH / 256, 256, 0, ctx->stream>>>(ctx->normalized, ctx->quantized);
            submitted = cudaGetLastError() == cudaSuccess;
        }
        if (submitted) {
            project<<<(ROWS + 7) / 8, 256, 0, ctx->stream>>>(
                static_cast<const Q6Block *>(weight), ctx->quantized, ctx->output);
            submitted = cudaGetLastError() == cudaSuccess;
        }
        if (submitted) {
            greedy_parts<<<GREEDY_BLOCKS, 256, 0, ctx->stream>>>(ctx->output, ctx->partials);
            submitted = cudaGetLastError() == cudaSuccess;
        }
        if (submitted) {
            greedy_finish<<<1, 256, 0, ctx->stream>>>(ctx->partials, ctx->choice);
            submitted = cudaGetLastError() == cudaSuccess;
        }
        // End capture on every submission path before waiting or destroying storage.
        const cudaError_t ended = cudaStreamEndCapture(ctx->stream, &tail.graph);
        if (!submitted || ended != cudaSuccess || tail.graph == nullptr
            || cudaGraphInstantiate(&tail.executable, tail.graph, 0) != cudaSuccess) {
            align_native_cuda_q6_tail_reset(ctx, kind);
            return 0;
        }
        for (int index = 0; index < 8; ++index) tail.pointers[index] = pointers[index];
        tail.epsilon = epsilon;
    }
    const bool submitted = cudaGraphLaunch(tail.executable, ctx->stream) == cudaSuccess
        && cudaMemcpyAsync(&ctx->host_choice, ctx->choice, sizeof(Choice),
            cudaMemcpyDeviceToHost, ctx->stream) == cudaSuccess;
    const cudaError_t completed = cudaStreamSynchronize(ctx->stream);
    if (!submitted || completed != cudaSuccess) return 0;
#if defined(ALIGN_NATIVE_CUDA_Q6_FORCE_COMPLETION_FAILURE)
    fprintf(stderr, "native_q6_head forced completion failure\n");
    fprintf(stderr, "native_ffn_tail forced completion failure\n");
    return 0;
#endif
    ctx->ready = ctx->choice_ready = true;
    return 1;
}

extern "C" int align_native_cuda_q6_head_read(void *opaque, void *output, size_t bytes) {
    auto *ctx = static_cast<Context *>(opaque);
    return ctx != nullptr && ctx->ready && ctx->output != nullptr && output != nullptr
        && bytes == ROWS * sizeof(float) && cudaSetDevice(ctx->device) == cudaSuccess
        && cudaMemcpy(output, ctx->output, bytes, cudaMemcpyDeviceToHost) == cudaSuccess;
}

extern "C" int align_native_cuda_q6_head_greedy(void *opaque, int64_t *token) {
    if (token == nullptr) return 0;
    *token = -1;
    auto *ctx = static_cast<Context *>(opaque);
    if (ctx == nullptr || !ctx->ready || ctx->partials == nullptr || ctx->choice == nullptr)
        return 0;
    ctx->ready = false;
#if defined(ALIGN_NATIVE_CUDA_Q6_FORCE_GREEDY_FAILURE)
    if (ctx->ffn == nullptr || ctx->last_tail) {
        fprintf(stderr, "native_q6_head forced greedy failure\n");
        if (ctx->last_tail) fprintf(stderr, "native_ffn_tail forced greedy failure\n");
        return 0;
    }
#endif
    if (!ctx->choice_ready) {
        if (cudaSetDevice(ctx->device) != cudaSuccess) return 0;
        const bool submitted = enqueue_choice(ctx);
        const cudaError_t completed = cudaStreamSynchronize(ctx->stream);
        if (!submitted || completed != cudaSuccess) return 0;
        ctx->choice_ready = true;
    }
    const Choice result = ctx->host_choice;
    if (result.index < 0 || result.index >= ROWS || !isfinite(result.value)) return 0;
    ctx->ready = true;
    *token = result.index;
    return 1;
}

extern "C" int align_native_cuda_q6_head_wait(void *opaque) {
    auto *ctx = static_cast<Context *>(opaque);
    return ctx != nullptr && cudaSetDevice(ctx->device) == cudaSuccess
        && cudaStreamSynchronize(ctx->stream) == cudaSuccess;
}

extern "C" void align_native_cuda_q6_head_close(void *opaque) {
    auto *ctx = static_cast<Context *>(opaque);
    if (ctx == nullptr) return;
    cudaSetDevice(ctx->device);
    if (ctx->stream != nullptr) cudaStreamSynchronize(ctx->stream);
    for (TailGraph &tail : ctx->tails) {
        if (tail.executable != nullptr) cudaGraphExecDestroy(tail.executable);
        if (tail.graph != nullptr) cudaGraphDestroy(tail.graph);
    }
    align_native_cuda_q40_ffn_close(ctx->ffn);
    if (ctx->normalized != nullptr) cudaFree(ctx->normalized);
    if (ctx->residual != nullptr) cudaFree(ctx->residual);
    if (ctx->output != nullptr) cudaFree(ctx->output);
    if (ctx->quantized != nullptr) cudaFree(ctx->quantized);
    if (ctx->partials != nullptr) cudaFree(ctx->partials);
    if (ctx->choice != nullptr) cudaFree(ctx->choice);
    if (ctx->stream != nullptr) cudaStreamDestroy(ctx->stream);
    delete ctx;
}
