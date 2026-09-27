#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <arm_neon.h>
#include <chrono>
#include <cmath>
#include <cfloat>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>

uint32_t scalar(const float *v, size_t n) {
    float best=-INFINITY; uint32_t index=UINT32_MAX;
    for (size_t i=0;i<n;i++) { if (!std::isfinite(v[i])) return UINT32_MAX;
        if (v[i]>best) { best=v[i]; index=(uint32_t)i; } }
    return index;
}
uint32_t neon(const float *v, size_t n) {
    float32x4_t best=vdupq_n_f32(-INFINITY);
    uint32x4_t index=vdupq_n_u32(UINT32_MAX);
    uint32x4_t bad=vdupq_n_u32(0);
    size_t i=0;
    for (;i+4<=n;i+=4) {
        float32x4_t x=vld1q_f32(v+i);
        bad=vorrq_u32(bad,vmvnq_u32(vcleq_f32(vabsq_f32(x),vdupq_n_f32(FLT_MAX))));
        uint32x4_t greater=vcgtq_f32(x,best);
        best=vbslq_f32(greater,x,best);
        uint32_t ids[4]={(uint32_t)i,(uint32_t)i+1,(uint32_t)i+2,(uint32_t)i+3};
        index=vbslq_u32(greater,vld1q_u32(ids),index);
    }
    uint32_t flags[4],indices[4];float values[4];
    vst1q_u32(flags,bad);vst1q_u32(indices,index);vst1q_f32(values,best);
    for (int lane=0;lane<4;lane++) if (flags[lane]) return UINT32_MAX;
    float maximum=-INFINITY;uint32_t result=UINT32_MAX;
    for (int lane=0;lane<4;lane++) if (values[lane]>maximum || (values[lane]==maximum && indices[lane]<result)) {
        maximum=values[lane];result=indices[lane];
    }
    for (;i<n;i++) {if (!std::isfinite(v[i])) return UINT32_MAX;
        if (v[i]>maximum) {maximum=v[i];result=(uint32_t)i;}}
    return result;
}
int main(int argc,char **argv) {
    if (argc<2) return 2;
    @autoreleasepool {
        id<MTLDevice> device=MTLCreateSystemDefaultDevice();id<MTLCommandQueue> queue=[device newCommandQueue];
        if (!device || !queue) return 1;
        puts("kind,path,iteration,order,wall_ns,token");
        for (int f=1;f<argc;f++) {
            std::ifstream stream(argv[f],std::ios::binary);
            std::vector<char> bytes((std::istreambuf_iterator<char>(stream)),std::istreambuf_iterator<char>());
            if (bytes.empty() || bytes.size()%4 || bytes.size()>4194304) return 1;
            size_t n=bytes.size()/4;auto *values=(float *)bytes.data();
            uint32_t want=scalar(values,n);
            if (want==UINT32_MAX || neon(values,n)!=want) return 1;
            values[1]=values[want]+1;values[n-2]=values[want]+1;
            if (scalar(values,n)!=1 || neon(values,n)!=1) return 1;
            values[17]=NAN;
            if (scalar(values,n)!=UINT32_MAX || neon(values,n)!=UINT32_MAX) return 1;
            values[17]=INFINITY;
            if (scalar(values,n)!=UINT32_MAX || neon(values,n)!=UINT32_MAX) return 1;
            stream.clear();stream.seekg(0);stream.read(bytes.data(),bytes.size());
            id<MTLBuffer> src=[device newBufferWithLength:bytes.size() options:MTLResourceStorageModeShared];
            id<MTLBuffer> dst=[device newBufferWithLength:bytes.size() options:MTLResourceStorageModeShared];
            if (!src || !dst) return 1;
            memcpy(src.contents,bytes.data(),bytes.size());
            auto run=[&](bool fast){
                auto start=std::chrono::steady_clock::now();
                id<MTLCommandBuffer> cb=[queue commandBuffer];id<MTLBlitCommandEncoder> enc=[cb blitCommandEncoder];
                [enc copyFromBuffer:src sourceOffset:0 toBuffer:dst destinationOffset:0 size:bytes.size()];
                [enc endEncoding];[cb commit];[cb waitUntilCompleted];
                if (cb.status!=MTLCommandBufferStatusCompleted) std::exit(1);
                uint32_t token=fast?neon((float *)dst.contents,n):scalar((float *)dst.contents,n);
                auto end=std::chrono::steady_clock::now();
                return std::pair<long long,uint32_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(end-start).count(),token);
            };
            for (int i=0;i<100;i++) if (run(false).second!=want || run(true).second!=want) return 1;
            for (int i=0;i<100;i++) {
                bool reversed=i%2;auto a=run(reversed),b=run(!reversed);
                if (a.second!=want || b.second!=want) return 1;
                auto old=reversed?b:a,newer=reversed?a:b;
                printf("control,%s,%d,%s,%lld,%u\n",argv[f],i,reversed?"candidate-first":"control-first",old.first,old.second);
                printf("candidate,%s,%d,%s,%lld,%u\n",argv[f],i,reversed?"candidate-first":"control-first",newer.first,newer.second);
            }
            fprintf(stderr,"correctness PASS: %s, %zu values, tie/NaN/Inf\n",argv[f],n);
        }
    }
    return 0;
}
