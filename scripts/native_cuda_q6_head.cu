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

#include <cuda_fp16.h>
#include <cuda_runtime.h>
#include <new>
#include <stdint.h>
#include <stdio.h>

namespace {
constexpr int WIDTH = 2048, ROWS = 248320;
struct Q6Block { uint8_t ql[128], qh[64]; int8_t scales[16]; __half d; };
struct Q8Block { int8_t q[32]; __half d, sum; };
static_assert(sizeof(Q6Block) == 210, "Q6_K block layout changed");
static_assert(sizeof(Q8Block) == 36, "Q8_1 block layout changed");

struct Context {
    cudaStream_t stream = nullptr;
    Q8Block *quantized = nullptr;
    int device = -1;
};

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
}  // namespace

extern "C" void *align_native_cuda_q6_head_open(int device_ordinal) {
    int count = 0;
    if (device_ordinal != 0 || cudaGetDeviceCount(&count) != cudaSuccess || count != 1
        || cudaSetDevice(device_ordinal) != cudaSuccess) return nullptr;
    auto *ctx = new (std::nothrow) Context;
    if (ctx == nullptr) return nullptr;
    ctx->device = device_ordinal;
    if (cudaStreamCreateWithFlags(&ctx->stream, cudaStreamNonBlocking) != cudaSuccess
        || cudaMalloc(&ctx->quantized, WIDTH / 32 * sizeof(Q8Block)) != cudaSuccess) {
        align_native_cuda_q6_head_close(ctx);
        return nullptr;
    }
    return ctx;
}

extern "C" int align_native_cuda_q6_head_run(void *opaque, const void *weight,
        const void *input, void *output) {
    auto *ctx = static_cast<Context *>(opaque);
    if (ctx == nullptr || ctx->stream == nullptr || ctx->quantized == nullptr
        || cudaSetDevice(ctx->device) != cudaSuccess
        || !device_pointer(weight, ctx->device) || !device_pointer(input, ctx->device)
        || !device_pointer(output, ctx->device)) return 0;
#if defined(ALIGN_NATIVE_CUDA_Q6_FORCE_SUBMIT_FAILURE)
    fprintf(stderr, "native_q6_head forced submit failure\n");
    return 0;
#endif
    quantize_input<<<WIDTH / 256, 256, 0, ctx->stream>>>(
        static_cast<const float *>(input), ctx->quantized);
    if (cudaGetLastError() != cudaSuccess) return 0;
    project<<<(ROWS + 7) / 8, 256, 0, ctx->stream>>>(
        static_cast<const Q6Block *>(weight), ctx->quantized, static_cast<float *>(output));
    if (cudaGetLastError() != cudaSuccess) {
        cudaStreamSynchronize(ctx->stream);
        return 0;
    }
    if (cudaStreamSynchronize(ctx->stream) != cudaSuccess) return 0;
#if defined(ALIGN_NATIVE_CUDA_Q6_FORCE_COMPLETION_FAILURE)
    fprintf(stderr, "native_q6_head forced completion failure\n");
    return 0;
#endif
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
    if (ctx->quantized != nullptr) cudaFree(ctx->quantized);
    if (ctx->stream != nullptr) cudaStreamDestroy(ctx->stream);
    delete ctx;
}
