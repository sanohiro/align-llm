#include "native_cuda_state_copy.h"

#include <cuda_runtime.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vector>

static void require(bool valid, const char *message) {
    if (!valid) {
        fprintf(stderr, "native CUDA state copy: %s\n", message);
        exit(1);
    }
}

int main() {
    constexpr size_t total = 3 * 1048576;
    uint8_t *source = nullptr, *destination = nullptr;
    require(cudaMalloc(&source, total) == cudaSuccess, "source allocation failed");
    require(cudaMalloc(&destination, total) == cudaSuccess, "destination allocation failed");
    std::vector<uint8_t> input(total), expected(total, 0), actual(total);
    for (size_t i = 0; i < total; ++i) input[i] = uint8_t((i * 37 + i / 4096) & 255);
    require(cudaMemcpy(source, input.data(), total, cudaMemcpyHostToDevice) == cudaSuccess,
        "source init failed");
    require(cudaMemset(destination, 0, total) == cudaSuccess, "destination init failed");
    void *context = align_native_cuda_copy_open(0);
    require(context != nullptr, "open failed");
    align_native_cuda_copy copies[2] = {
        {0, 1048576, 1048576},
        {1048576, 0, 1048576},
    };
    require(!align_native_cuda_copy_submit(context, source, total, destination, total,
        copies, 0), "empty batch accepted");
    require(align_native_cuda_copy_submit(context, source, total, destination, total,
        copies, 2), "batch submission failed");
    require(!align_native_cuda_copy_submit(context, source, total, destination, total,
        copies, 2), "overlapping pending batch accepted");
    require(align_native_cuda_copy_wait(context), "batch completion failed");
    memcpy(expected.data(), input.data() + 1048576, 1048576);
    memcpy(expected.data() + 1048576, input.data(), 1048576);
    require(cudaMemcpy(actual.data(), destination, total, cudaMemcpyDeviceToHost) == cudaSuccess,
        "readback failed");
    require(actual == expected, "full vectorized copy or untouched range differs");
    align_native_cuda_copy outside = {total - 10, 0, 20};
    align_native_cuda_copy overlap = {0, 1, 1048576};
    align_native_cuda_copy duplicate[2] = {
        {0, 0, 1048576}, {1048576, 524288, 1048576},
    };
    require(!align_native_cuda_copy_submit(context, source, total, destination, total,
        &outside, 1), "out-of-range descriptor accepted");
    require(!align_native_cuda_copy_submit(context, destination, total, destination, total,
        &overlap, 1), "overlapping copy accepted");
    require(!align_native_cuda_copy_submit(context, source, total, destination, total,
        duplicate, 2), "overlapping destinations accepted");
    require(align_native_cuda_copy_submit(context, source, total, destination, total,
        copies, 2) && align_native_cuda_copy_wait(context), "repeated batch failed");
    align_native_cuda_copy unaligned = {2 * 1048576 + 3, 2 * 1048576 + 7, 513};
    require(align_native_cuda_copy_submit(context, source, total, destination, total,
        &unaligned, 1) && align_native_cuda_copy_wait(context), "unaligned fallback failed");
    memcpy(expected.data() + unaligned.destination_offset,
        input.data() + unaligned.source_offset, unaligned.bytes);
    require(cudaMemcpy(actual.data(), destination, total, cudaMemcpyDeviceToHost) == cudaSuccess,
        "fallback readback failed");
    require(actual == expected, "fallback copy or untouched range differs");
    align_native_cuda_copy_close(context);
    require(cudaFree(destination) == cudaSuccess, "destination release failed");
    require(cudaFree(source) == cudaSuccess, "source release failed");
    puts("native CUDA state copy: PASS");
    return 0;
}
