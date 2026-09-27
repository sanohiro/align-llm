// Developer probe: borrow a ggml Metal shared allocation into an independent
// Metal command queue without copying its bytes or using ggml Metal internals.
// clang++ -O2 -std=c++17 -fobjc-arc -framework Foundation -framework Metal \
//   -I GGML/ggml/include -L BUNDLE -Wl,-rpath,BUNDLE -lggml -lggml-base \
//   scripts/metal-native-buffer-bridge.mm -o /tmp/metal-native-buffer-bridge
// /tmp/metal-native-buffer-bridge BUNDLE/libggml-metal.so

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include "ggml.h"
#include "ggml-backend.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <vector>

static void require(bool condition, const char *message) {
    if (!condition) {
        std::fprintf(stderr, "metal-native-buffer-bridge: %s\n", message);
        std::exit(1);
    }
}

int main(int argc, char **argv) {
    require(argc == 2, "usage: metal-native-buffer-bridge LIBGGML_METAL_SO");
    @autoreleasepool {
        constexpr size_t count = 262144;
        constexpr size_t bytes = count * sizeof(float);
        ggml_backend_reg_t reg = ggml_backend_load(argv[1]);
        require(reg != nullptr, "Metal plugin load failed");
        ggml_backend_dev_t device = ggml_backend_reg_dev_get(reg, 0);
        ggml_backend_t backend = ggml_backend_dev_init(device, nullptr);
        require(backend != nullptr, "Metal backend initialization failed");
        ggml_init_params params = {ggml_tensor_overhead() * 4, nullptr, true};
        ggml_context *ctx = ggml_init(params);
        require(ctx != nullptr, "ggml metadata allocation failed");
        ggml_tensor *source = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, count);
        ggml_tensor *destination = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, count);
        ggml_backend_buffer_t allocation = ggml_backend_alloc_ctx_tensors(ctx, backend);
        require(allocation != nullptr, "shared Metal allocation failed");
        const char *name = ggml_backend_buft_name(ggml_backend_buffer_get_type(allocation));
        require(name != nullptr && std::strstr(name, "MTL") != nullptr &&
                std::strstr(name, "Private") == nullptr, "allocation is not shared Metal");
        void *base = ggml_backend_buffer_get_base(allocation);
        size_t size = ggml_backend_buffer_get_size(allocation);
        size_t page = size_t(getpagesize());
        require(base != nullptr && page != 0 &&
                reinterpret_cast<uintptr_t>(base) % page == 0,
                "allocation base is not page aligned");
        require(source->data != nullptr && destination->data != nullptr &&
                uintptr_t(source->data) >= uintptr_t(base) &&
                uintptr_t(destination->data) >= uintptr_t(base),
                "tensor is outside allocation");
        size_t source_offset = uintptr_t(source->data) - uintptr_t(base);
        size_t destination_offset = uintptr_t(destination->data) - uintptr_t(base);
        require(source_offset <= size && bytes <= size - source_offset &&
                destination_offset <= size && bytes <= size - destination_offset,
                "tensor extent is outside allocation");

        std::vector<float> input(count), output(count, -1.0f);
        for (size_t i = 0; i < count; ++i) input[i] = float((i * 257) % 65521) / 1024.0f;
        ggml_backend_tensor_set(source, input.data(), 0, bytes);
        ggml_backend_tensor_set(destination, output.data(), 0, bytes);
        ggml_backend_synchronize(backend);

        id<MTLDevice> metal = MTLCreateSystemDefaultDevice();
        require(metal != nil, "system Metal device unavailable");
        size_t wrapped_length = size - size % page;
        require(wrapped_length > source_offset && bytes <= wrapped_length - source_offset &&
                wrapped_length > destination_offset && bytes <= wrapped_length - destination_offset,
                "page-aligned view does not cover both tensors");
        // The ggml allocation remains the owner and outlives this borrowed view.
        id<MTLBuffer> view = [metal newBufferWithBytesNoCopy:base
                                                     length:wrapped_length
                                                    options:MTLResourceStorageModeShared
                                                deallocator:^(void *, NSUInteger) {}];
        require(view != nil && view.contents == base, "zero-copy Metal view refused");
        NSString *source_code = @"#include <metal_stdlib>\n"
            "using namespace metal;\n"
            "kernel void linear_copy(device const float *src [[buffer(0)]], "
            "device float *dst [[buffer(1)]], uint i [[thread_position_in_grid]]) "
            "{ if (i < 262144) dst[i] = src[i]; }\n";
        NSError *error = nil;
        id<MTLLibrary> library = [metal newLibraryWithSource:source_code options:nil error:&error];
        require(library != nil, "native Metal kernel compilation failed");
        id<MTLComputePipelineState> pipeline =
            [metal newComputePipelineStateWithFunction:[library newFunctionWithName:@"linear_copy"]
                                                  error:&error];
        require(pipeline != nil, "native Metal pipeline creation failed");
        id<MTLCommandQueue> queue = [metal newCommandQueue];
        require(queue != nil, "native Metal queue creation failed");
        id<MTLCommandBuffer> command = [queue commandBuffer];
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        [encoder setComputePipelineState:pipeline];
        [encoder setBuffer:view offset:source_offset atIndex:0];
        [encoder setBuffer:view offset:destination_offset atIndex:1];
        [encoder dispatchThreads:MTLSizeMake(count, 1, 1)
          threadsPerThreadgroup:MTLSizeMake(256, 1, 1)];
        [encoder endEncoding];
        [command commit];
        [command waitUntilCompleted];
        require(command.status == MTLCommandBufferStatusCompleted,
                "native Metal execution failed");
        ggml_backend_tensor_get(destination, output.data(), 0, bytes);
        require(std::memcmp(input.data(), output.data(), bytes) == 0,
                "independent Metal copy did not update ggml tensor bytes");
        std::printf("native_bridge=PASS bytes=%zu source_offset=%zu destination_offset=%zu\n",
                    bytes, source_offset, destination_offset);
        view = nil;
        ggml_backend_buffer_free(allocation);
        ggml_free(ctx);
        ggml_backend_free(backend);
    }
    return 0;
}
