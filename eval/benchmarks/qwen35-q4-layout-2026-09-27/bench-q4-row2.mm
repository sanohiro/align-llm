// Local actual-weight Q4_0 resident-layout experiment. Not a runtime backend.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "ggml.h"
#include "ggml-backend.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

static constexpr int WARMUPS = 12, PAIRS = 5, ITERATIONS = 20;
static const char *shader = R"METAL(
#include <metal_stdlib>
using namespace metal;

template<bool SPLIT, ushort NROWS>
inline void q4_impl(
    device const uchar *raw, device const half *scales, device const uchar *quants,
    device const float *input, device float *output, uint width, uint rows,
    uint group, ushort lane, ushort simd) {
    const uint first_row = (group * 2 + simd) * NROWS;
    if (first_row >= rows) return;
    const uint blocks_per_row = width / 32;
    const ushort block_lane = lane / 2;
    const ushort half_lane = lane % 2;
    const ushort il = half_lane * 8;
    float sum[NROWS] = {0.f};
    for (uint block = block_lane; block < blocks_per_row; block += 16) {
        device const float *y = input + block * 32 + il;
        float yl[16], sumy = 0.f;
        for (ushort i = 0; i < 8; i += 2) {
            const float a = y[i], b = y[i+1], c = y[i+16], d = y[i+17];
            sumy += a + b;
            sumy += c + d;
            yl[i] = a; yl[i+1] = b / 256.f;
            yl[i+8] = c / 16.f; yl[i+9] = d / 4096.f;
        }
        for (ushort row = 0; row < NROWS; ++row) {
            if (first_row + row >= rows) continue;
            const uint index = (first_row + row) * blocks_per_row + block;
            const float scale = SPLIT ? float(scales[index]) :
                float(*reinterpret_cast<device const half *>(raw + index * 18));
            device const ushort *qs = SPLIT ?
                reinterpret_cast<device const ushort *>(quants + index * 16 + il) :
                reinterpret_cast<device const ushort *>(raw + index * 18 + 2 + il);
            float acc[4] = {0.f};
            for (ushort i = 0; i < 8; i += 2) {
                const ushort q = qs[i / 2];
                acc[0] += yl[i] * float(q & 0x000f);
                acc[1] += yl[i+1] * float(q & 0x0f00);
                acc[2] += yl[i+8] * float(q & 0x00f0);
                acc[3] += yl[i+9] * float(q & 0xf000);
            }
            sum[row] += scale * (sumy * -8.f + acc[0] + acc[1] + acc[2] + acc[3]);
        }
    }
    for (ushort row = 0; row < NROWS; ++row) {
        const float total = simd_sum(sum[row]);
        if (lane == 0 && first_row + row < rows) output[first_row + row] = total;
    }
}

kernel void q4_raw(device const uchar *raw [[buffer(0)]],
    device const half *scales [[buffer(1)]], device const uchar *quants [[buffer(2)]],
    device const float *input [[buffer(3)]], device float *output [[buffer(4)]],
    constant uint &width [[buffer(5)]], constant uint &rows [[buffer(6)]],
    uint group [[threadgroup_position_in_grid]],
    ushort lane [[thread_index_in_simdgroup]],
    ushort simd [[simdgroup_index_in_threadgroup]]) {
    q4_impl<false, 4>(raw, scales, quants, input, output, width, rows, group, lane, simd);
}

kernel void q4_row2(device const uchar *raw [[buffer(0)]],
    device const half *scales [[buffer(1)]], device const uchar *quants [[buffer(2)]],
    device const float *input [[buffer(3)]], device float *output [[buffer(4)]],
    constant uint &width [[buffer(5)]], constant uint &rows [[buffer(6)]],
    uint group [[threadgroup_position_in_grid]],
    ushort lane [[thread_index_in_simdgroup]],
    ushort simd [[simdgroup_index_in_threadgroup]]) {
    q4_impl<false, 2>(raw, scales, quants, input, output, width, rows, group, lane, simd);
}
)METAL";

static void need(bool ok, const char *message) {
    if (!ok) { std::fprintf(stderr, "Q4_SPLIT error=%s\n", message); std::exit(1); }
}
static std::vector<uint8_t> read(const std::string &path, size_t bytes) {
    std::ifstream file(path, std::ios::binary | std::ios::ate);
    need(bool(file) && file.tellg() == std::streamoff(bytes), "capture extent differs");
    file.seekg(0);
    std::vector<uint8_t> data(bytes);
    file.read(reinterpret_cast<char *>(data.data()), bytes);
    need(bool(file), "capture read failed");
    return data;
}
static double millis(std::chrono::steady_clock::time_point start) {
    return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now()-start).count();
}
struct Timing { double wall_ms, gpu_ms; };

int main(int argc, char **argv) {
    need(argc == 7, "usage: bench-q4-split PLUGIN CAPTURE_DIR LAYER ROLE WIDTH ROWS");
    const std::string dir = argv[2], layer = argv[3], role = argv[4];
    const bool rotate = layer == "all";
    const int layer_count = rotate ? 24 : 1;
    const int width = std::atoi(argv[5]), rows = std::atoi(argv[6]);
    need((role == "gate" || role == "down") && (!rotate || role == "gate") &&
         width > 0 && rows > 0 &&
         width % 32 == 0 && rows % 4 == 0, "unsupported role or shape");
    const size_t blocks = size_t(width / 32) * rows;
    const size_t weight_bytes = blocks * 18, input_size = size_t(width) * 4;
    std::vector<uint8_t> raw(weight_bytes * layer_count), input_bytes(input_size * layer_count);
    for (int l=0;l<layer_count;++l) {
        const std::string name = rotate ? (l<10 ? "0" : "") + std::to_string(l) : layer;
        auto weight = read(dir + "/" + name + "-" + role + ".bin",weight_bytes);
        auto input = read(dir + "/" + name + (role == "gate" ? "-input.bin" : "-gated.bin"),input_size);
        std::memcpy(raw.data()+l*weight_bytes,weight.data(),weight_bytes);
        std::memcpy(input_bytes.data()+l*input_size,input.data(),input_size);
    }
    @autoreleasepool {
        auto reg = ggml_backend_load(argv[1]); need(reg, "pinned Metal plugin load failed");
        auto backend = ggml_backend_dev_init(ggml_backend_reg_dev_get(reg, 0), nullptr);
        need(backend, "ggml backend init failed");
        auto ctx = ggml_init({ggml_tensor_overhead()*12+ggml_graph_overhead_custom(12,false),nullptr,true});
        need(ctx, "ggml context init failed");
        auto w = ggml_new_tensor_2d(ctx,GGML_TYPE_Q4_0,width,rows);
        auto x = ggml_new_tensor_1d(ctx,GGML_TYPE_F32,width);
        auto y = ggml_mul_mat(ctx,w,x);
        auto graph = ggml_new_graph_custom(ctx,12,false);
        ggml_build_forward_expand(graph,y);
        auto buffer = ggml_backend_alloc_ctx_tensors(ctx,backend);
        need(buffer && ggml_nbytes(w)==weight_bytes, "ggml allocation or extent failed");
        ggml_backend_tensor_set(w,raw.data(),0,weight_bytes);
        ggml_backend_tensor_set(x,input_bytes.data(),0,input_size);

        auto conversion_start = std::chrono::steady_clock::now();
        std::vector<uint16_t> scales(blocks*layer_count);
        std::vector<uint8_t> quants(blocks*16*layer_count);
        for (size_t i=0;i<blocks*layer_count;++i) {
            std::memcpy(&scales[i],raw.data()+18*i,2);
            std::memcpy(quants.data()+16*i,raw.data()+18*i+2,16);
        }
        const double conversion_ms = millis(conversion_start);
        for (size_t i=0;i<blocks*layer_count;++i) {
            need(std::memcmp(&scales[i],raw.data()+18*i,2)==0 &&
                 std::memcmp(quants.data()+16*i,raw.data()+18*i+2,16)==0,
                 "lossless repack check failed");
        }

        id<MTLDevice> metal=MTLCreateSystemDefaultDevice(); need(metal!=nil,"Metal device missing");
        NSError *error=nil;
        id<MTLLibrary> library=[metal newLibraryWithSource:[NSString stringWithUTF8String:shader]
                                                options:nil error:&error];
        if(!library)std::fprintf(stderr,"Metal compile: %s\n",error.localizedDescription.UTF8String);
        need(library!=nil,"Metal library compile failed");
        id<MTLComputePipelineState> pipes[2];
        pipes[0]=[metal newComputePipelineStateWithFunction:[library newFunctionWithName:@"q4_raw"] error:&error];
        pipes[1]=[metal newComputePipelineStateWithFunction:[library newFunctionWithName:@"q4_row2"] error:&error];
        need(pipes[0]!=nil && pipes[1]!=nil && pipes[0].threadExecutionWidth==32 &&
             pipes[1].threadExecutionWidth==32 && pipes[0].maxTotalThreadsPerThreadgroup>=64 &&
             pipes[1].maxTotalThreadsPerThreadgroup>=64,"Metal pipeline geometry invalid");
        id<MTLCommandQueue> queue=[metal newCommandQueue];
        id<MTLBuffer> mw=[metal newBufferWithBytes:raw.data() length:raw.size()
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> mw_alt=[metal newBufferWithBytes:raw.data() length:raw.size()
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> ms=[metal newBufferWithBytes:scales.data() length:scales.size()*2
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> mq=[metal newBufferWithBytes:quants.data() length:quants.size()
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> mx=[metal newBufferWithBytes:input_bytes.data() length:input_bytes.size()
            options:MTLResourceStorageModeShared];
        id<MTLBuffer> my[2] = {
            [metal newBufferWithLength:size_t(rows)*4 options:MTLResourceStorageModeShared],
            [metal newBufferWithLength:size_t(rows)*4 options:MTLResourceStorageModeShared]};
        need(queue && mw && mw_alt && ms && mq && mx && my[0] && my[1],"Metal buffer allocation failed");
        std::printf("{\"event\":\"setup\",\"role\":\"%s\",\"layer\":\"%s\",\"width\":%d,\"rows\":%d,"
                    "\"layers\":%d,\"raw_bytes\":%zu,\"raw_bytes_per_layer\":%zu,"
                    "\"split_scale_bytes\":%zu,\"split_quant_bytes\":%zu,"
                    "\"conversion_ms\":%.9f,\"ggml_buffer_bytes\":%zu,\"threads\":64,"
                    "\"warmups\":%d,\"pairs\":%d,\"iterations_per_pair\":%d}\n",
                    role.c_str(),layer.c_str(),width,rows,layer_count,raw.size(),weight_bytes,
                    scales.size()*2,quants.size(),
                    conversion_ms,ggml_backend_buffer_get_size(buffer),WARMUPS,PAIRS,ITERATIONS);
        auto run=[&](int arm,int layer_index)->Timing {
            auto start=std::chrono::steady_clock::now();
            if(arm==0) {
                if(rotate) {
                    ggml_backend_tensor_set(w,raw.data()+layer_index*weight_bytes,0,weight_bytes);
                    ggml_backend_tensor_set(x,input_bytes.data()+layer_index*input_size,0,input_size);
                }
                need(ggml_backend_graph_compute(backend,graph)==GGML_STATUS_SUCCESS,"ggml compute failed");
                return {millis(start),-1};
            }
            const int index=arm-1;
            id<MTLCommandBuffer> command=[queue commandBuffer];
            id<MTLComputeCommandEncoder> encoder=[command computeCommandEncoder];
            need(command && encoder,"Metal command creation failed");
            uint32_t gpu_width=width,gpu_rows=rows;
            [encoder setComputePipelineState:pipes[index]];
            [encoder setBuffer:index==0?mw:mw_alt offset:layer_index*weight_bytes atIndex:0];
            [encoder setBuffer:ms offset:layer_index*blocks*2 atIndex:1];
            [encoder setBuffer:mq offset:layer_index*blocks*16 atIndex:2];
            [encoder setBuffer:mx offset:layer_index*input_size atIndex:3];
            [encoder setBuffer:my[index] offset:0 atIndex:4];
            [encoder setBytes:&gpu_width length:sizeof(gpu_width) atIndex:5];
            [encoder setBytes:&gpu_rows length:sizeof(gpu_rows) atIndex:6];
            [encoder dispatchThreadgroups:MTLSizeMake(index==0?(rows+7)/8:(rows+3)/4,1,1)
                threadsPerThreadgroup:MTLSizeMake(64,1,1)];
            [encoder endEncoding];[command commit];[command waitUntilCompleted];
            need(command.status==MTLCommandBufferStatusCompleted,"Metal command failed");
            double gpu=-1;
            if(command.GPUStartTime>0 && command.GPUEndTime>command.GPUStartTime)
                gpu=1000*(command.GPUEndTime-command.GPUStartTime);
            return {millis(start),gpu};
        };
        std::vector<float> reference(rows);
        for(int l=0;l<layer_count;++l) {
          run(0,l);run(1,l);run(2,l);
          ggml_backend_tensor_get(y,reference.data(),0,rows*4);
          if(role=="down") {
            auto captured=read(dir+"/"+layer+"-output.bin",size_t(rows)*4);
            const float *values=reinterpret_cast<const float *>(captured.data());
            double max_abs=0;
            for(int i=0;i<rows;++i) {
                double diff=std::abs(double(values[i])-reference[i]);
                need(std::isfinite(values[i]) && diff<=0.005+0.0005*std::abs(double(reference[i])),
                     "captured down differs from local ggml graph");
                max_abs=std::max(max_abs,diff);
            }
            std::printf("{\"event\":\"check\",\"arm\":\"captured_down\",\"count\":%d,\"max_abs\":%.9g}\n",rows,max_abs);
          }
          for(int arm=1;arm<=2;++arm) {
            const float *values=static_cast<const float *>(my[arm-1].contents);
            double max_abs=0;
            for(int i=0;i<rows;++i) {
                double diff=std::abs(double(values[i])-reference[i]);
                need(std::isfinite(values[i]) && diff<=0.005+0.0005*std::abs(double(reference[i])),
                     "native output exceeds predeclared bound");
                max_abs=std::max(max_abs,diff);
            }
            std::printf("{\"event\":\"check\",\"layer\":%d,\"arm\":\"%s\",\"count\":%d,\"max_abs\":%.9g}\n",
                        l,arm==1?"row4":"row2",rows,max_abs);
          }
        }
        for(int i=0;i<WARMUPS;++i)for(int arm=rotate?1:0;arm<3;++arm)run(arm,i%layer_count);
        for(int pair=0;pair<PAIRS;++pair) {
            double wall[3]={0},gpu[3]={0};
            for(int i=0;i<ITERATIONS;++i)for(int order=0;order<(rotate?2:3);++order) {
                int arm=rotate?1+(pair+order)%2:(pair+order)%3;
                int l=(pair*ITERATIONS+i)%layer_count;
                Timing t=run(arm,l); wall[arm]+=t.wall_ms; if(t.gpu_ms>=0)gpu[arm]+=t.gpu_ms;
                std::printf("{\"event\":\"sample\",\"pair\":%d,\"iteration\":%d,\"layer\":%d,\"arm\":\"%s\","
                            "\"wall_ms\":%.9f,\"gpu_ms\":%.9f}\n",pair,i,l,
                            arm==0?"ggml":arm==1?"row4":"row2",t.wall_ms,t.gpu_ms);
            }
            std::printf("{\"event\":\"pair\",\"pair\":%d,\"ggml_wall_ms\":%.9f,"
                        "\"row4_wall_ms\":%.9f,\"row2_wall_ms\":%.9f,"
                        "\"row4_gpu_ms\":%.9f,\"row2_gpu_ms\":%.9f}\n",pair,
                        rotate?-1:wall[0]/ITERATIONS,wall[1]/ITERATIONS,wall[2]/ITERATIONS,
                        gpu[1]/ITERATIONS,gpu[2]/ITERATIONS);
        }
        ggml_backend_buffer_free(buffer);ggml_free(ctx);ggml_backend_free(backend);
        std::printf("{\"event\":\"complete\"}\n");
    }
    return 0;
}
