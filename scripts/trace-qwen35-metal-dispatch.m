/* Diagnostic-only Metal pipeline/dispatch census; never use its clocks for speed.
 * Compile with Q35_TRACE_LLAMA for the pinned reference, which has no Align ABI.
 * The same C/ObjC source then records function and launch signatures in both.
 */
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
static void (*orig_set)(id,SEL,id<MTLComputePipelineState>);
static void (*orig_dispatch)(id,SEL,MTLSize,MTLSize);
static void (*orig_barrier)(id,SEL,MTLBarrierScope);
static id<MTLComputePipelineState> (*orig_new_pipeline)(id,SEL,id<MTLFunction>,NSError **);
static char pipeline_key;
static char function_name_key;
static id<MTLComputePipelineState> traced_new_pipeline(id object,SEL selector,id<MTLFunction> function,NSError **error) {
 id<MTLComputePipelineState> pipeline=orig_new_pipeline(object,selector,function,error);
 if(pipeline)objc_setAssociatedObject(pipeline,&function_name_key,function.name,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
 return pipeline;
}
static void traced_set(id object,SEL selector,id<MTLComputePipelineState> pipeline) {
 NSString *label=objc_getAssociatedObject(pipeline,&function_name_key) ?: pipeline.label ?: @"(unlabeled)";
 objc_setAssociatedObject(object,&pipeline_key,label,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
 orig_set(object,selector,pipeline);
}
static void traced_dispatch(id object,SEL selector,MTLSize groups,MTLSize threads) {
 NSString *label=objc_getAssociatedObject(object,&pipeline_key);
 fprintf(stderr,"Q35_KERNEL label=%s groups=%lu,%lu,%lu threads=%lu,%lu,%lu\n",
   (label ?: @"(unset)").UTF8String,(unsigned long)groups.width,(unsigned long)groups.height,(unsigned long)groups.depth,
   (unsigned long)threads.width,(unsigned long)threads.height,(unsigned long)threads.depth);
 orig_dispatch(object,selector,groups,threads);
}
static void traced_barrier(id object,SEL selector,MTLBarrierScope scope) {
 fprintf(stderr,"Q35_BARRIER scope=%lu\n",(unsigned long)scope);
 orig_barrier(object,selector,scope);
}
__attribute__((constructor)) static void install(void) {
 @autoreleasepool {
  id<MTLDevice>d=MTLCreateSystemDefaultDevice();id<MTLCommandQueue>q=[d newCommandQueue];
  id<MTLCommandBuffer>c=[q commandBuffer];id<MTLComputeCommandEncoder>e=[c computeCommandEncoder];
  Class cls=object_getClass(e);
  Class device_cls=object_getClass(d);
  Method pipeline_method=class_getInstanceMethod(device_cls,@selector(newComputePipelineStateWithFunction:error:));
  if(!pipeline_method){fprintf(stderr,"Q35_KERNEL pipeline_factory_unavailable\n");abort();}
  orig_new_pipeline=(void *)method_setImplementation(pipeline_method,(IMP)traced_new_pipeline);
  Method a=class_getInstanceMethod(cls,@selector(setComputePipelineState:));
  Method b=class_getInstanceMethod(cls,@selector(dispatchThreadgroups:threadsPerThreadgroup:));
  Method barrier=class_getInstanceMethod(cls,@selector(memoryBarrierWithScope:));
  if(!a || !b || !barrier){fprintf(stderr,"Q35_KERNEL unavailable\n");abort();}
  orig_set=(void *)method_setImplementation(a,(IMP)traced_set);
  orig_dispatch=(void *)method_setImplementation(b,(IMP)traced_dispatch);
  orig_barrier=(void *)method_setImplementation(barrier,(IMP)traced_barrier);
  fprintf(stderr,"Q35_KERNEL installed class=%s\n",class_getName(cls));
  [e endEncoding];
 }
}
#ifndef Q35_TRACE_LLAMA
#define INTERPOSE(replacement, original) \
 __attribute__((used)) static struct { const void *a; const void *b; } \
 interpose_##original __attribute__((section("__DATA,__interpose"))) = \
 {(const void *)(unsigned long)&replacement,(const void *)(unsigned long)&original}
extern int32_t align_gpu_graph_compute(void *, int32_t, const void *, int64_t, void *);
static int32_t graph(void *owner,int32_t kind,const void *key,int64_t length,void *value) {
 fprintf(stderr,"Q35_GRAPH_BEGIN kind=%d\n",kind);
 int32_t result=align_gpu_graph_compute(owner,kind,key,length,value);
 fprintf(stderr,"Q35_GRAPH_END kind=%d status=%d\n",kind,result);
 return result;
}
INTERPOSE(graph,align_gpu_graph_compute);
#endif
