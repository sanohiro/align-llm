// Standalone local Metal descriptor and odd-row smoke for the independent copy seam.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "native_metal_state_copy.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <unistd.h>

static void require(bool condition, const char *message) {
    if (!condition) { std::fprintf(stderr, "%s\n", message); std::exit(1); }
}

int main() {
    @autoreleasepool {
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        require(device != nil, "Metal device unavailable");
        void *context = align_native_metal_copy_open(device.name.UTF8String);
        require(context != nullptr, "native copy device selection failed");
        require(align_native_metal_copy_enable_strided(context), "strided pipeline unavailable");
        const size_t capacity = size_t(getpagesize()) * 128;
        void *source = nullptr, *destination = nullptr;
        require(posix_memalign(&source, size_t(getpagesize()), capacity) == 0, "source allocation failed");
        require(posix_memalign(&destination, size_t(getpagesize()), capacity) == 0, "destination allocation failed");
        auto *input = static_cast<unsigned char *>(source);
        auto *output = static_cast<unsigned char *>(destination);
        constexpr uint32_t rows = 37, elements = 5, input_stride = 28, output_stride = 20;
        align_native_metal_strided_copy item{64, 128, elements, rows, input_stride, output_stride};
        for (unsigned trial = 0; trial < 2; ++trial) {
            std::memset(input, 0x61, capacity);
            std::memset(output, 0x35, capacity);
            for (uint32_t row = 0; row < rows; ++row)
                for (uint32_t byte = 0; byte < elements * sizeof(float); ++byte)
                    input[item.source_offset + row * input_stride + byte] =
                        static_cast<unsigned char>((row * 19 + byte + trial) & 255);
            require(align_native_metal_copy_submit(context, source, capacity, destination, capacity,
                                                   nullptr, 0, &item, 1, nullptr), "odd-row submit failed");
            require(align_native_metal_copy_wait(context), "odd-row completion failed");
            for (size_t byte = 0; byte < capacity; ++byte) {
                unsigned char expected = 0x35;
                if (byte >= item.destination_offset &&
                    byte < item.destination_offset + rows * output_stride) {
                    size_t offset = byte - item.destination_offset;
                    expected = input[item.source_offset + (offset / output_stride) * input_stride
                                     + offset % output_stride];
                }
                require(output[byte] == expected, "odd-row payload or guard mismatch");
            }
        }
        align_native_metal_strided_copy row3{64, 128, 3, 6144, 16, 12};
        std::memset(input, 0x61, capacity);
        std::memset(output, 0x35, capacity);
        for (uint32_t row = 0; row < row3.rows; ++row)
            for (uint32_t byte = 0; byte < row3.row_elements * sizeof(float); ++byte)
                input[row3.source_offset + row * row3.source_row_stride + byte] =
                    static_cast<unsigned char>((row * 7 + byte) & 255);
        require(align_native_metal_copy_submit(context, source, capacity, destination, capacity,
                                               nullptr, 0, &row3, 1, nullptr), "three-element submit failed");
        require(align_native_metal_copy_wait(context), "three-element completion failed");
        for (uint32_t row = 0; row < row3.rows; ++row)
            for (uint32_t byte = 0; byte < row3.row_elements * sizeof(float); ++byte)
                require(output[row3.destination_offset + row * row3.destination_row_stride + byte]
                        == input[row3.source_offset + row * row3.source_row_stride + byte],
                        "three-element row mismatch");
        require(output[row3.destination_offset - 1] == 0x35
                && output[row3.destination_offset + row3.rows * row3.destination_row_stride] == 0x35,
                "three-element guards changed");
        item.source_row_stride = 16;
        require(!align_native_metal_copy_submit(context, source, capacity, destination, capacity,
                                                nullptr, 0, &item, 1, nullptr), "invalid stride was accepted");
        require(align_native_metal_copy_enable_greedy(context), "greedy pipelines unavailable");
        item.source_row_stride = input_stride;
        align_native_metal_greedy_input greedy{source, capacity, 4096, 65537};
        auto *values = reinterpret_cast<float *>(input + greedy.offset);
        for (uint32_t i = 0; i < greedy.count; ++i) values[i] = float(i % 11);
        values[5] = 100.0f;
        values[65536] = 100.0f;
        require(align_native_metal_copy_submit(context, source, capacity, destination, capacity,
                                               nullptr, 0, &item, 1, &greedy), "greedy submit failed");
        require(align_native_metal_copy_wait(context), "greedy completion failed");
        require(align_native_metal_copy_greedy_result(context) == 5, "first-index tie changed");
        require(align_native_metal_copy_greedy_result(context) == -1, "stale token remained");
        values[4097] = std::numeric_limits<float>::quiet_NaN();
        require(align_native_metal_copy_submit(context, source, capacity, destination, capacity,
                                               nullptr, 0, &item, 1, &greedy), "NaN submit failed");
        require(align_native_metal_copy_wait(context), "NaN completion failed");
        require(align_native_metal_copy_greedy_result(context) == -2, "NaN was accepted");
        values[4097] = std::numeric_limits<float>::infinity();
        require(align_native_metal_copy_submit(context, source, capacity, destination, capacity,
                                               nullptr, 0, &item, 1, &greedy), "infinity submit failed");
        require(align_native_metal_copy_wait(context), "infinity completion failed");
        require(align_native_metal_copy_greedy_result(context) == -2, "infinity was accepted");
        require(align_native_metal_copy_reset_views(context), "view reset failed");
        align_native_metal_copy_close(context);
        free(source);
        free(destination);
        std::puts("Metal copy PASS: 37x5 and 6144x3 bits, guards, reuse, invalid stride, greedy tie/nonfinite");
    }
}
