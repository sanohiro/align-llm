// Independent macOS diagnostic, injected only into a disposable measurement process.
// Build: clang -O2 -fblocks -dynamiclib -undefined dynamic_lookup \
//   -framework Foundation -framework Metal scripts/trace-metal-command-buffers.m -o trace.dylib
// Run with DYLD_INSERT_LIBRARIES=/absolute/path/trace.dylib. Never use these
// instrumented clocks as uninstrumented throughput evidence. _MTLCommandBuffer
// is a private implementation class; missing hooks mean unavailable evidence.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <stdatomic.h>
#include <mach/mach_time.h>
#include <stdio.h>

static void (*original_commit)(id, SEL);
static _Atomic unsigned long serial;

static double now(void) {
    mach_timebase_info_data_t base;
    mach_timebase_info(&base);
    return (double) mach_absolute_time() * base.numer / base.denom / 1e9;
}

static void traced_commit(id<MTLCommandBuffer> object, SEL selector) {
    unsigned long number = atomic_fetch_add(&serial, 1);
    double submitted = now();
    // Read timestamps only on completion. Do not add another GPU wait or dispatch.
    [object addCompletedHandler:^(id<MTLCommandBuffer> completed) {
        fprintf(stderr, "METAL_CB id=%lu submit=%.9f gpu_start=%.9f gpu_end=%.9f completed=%.9f status=%lu\n",
                number, submitted, completed.GPUStartTime, completed.GPUEndTime,
                now(), (unsigned long) completed.status);
    }];
    original_commit(object, selector);
}

__attribute__((constructor)) static void install(void) {
    Class cls = objc_getClass("_MTLCommandBuffer");
    Method method = class_getInstanceMethod(cls, @selector(commit));
    if (!method) {
        fprintf(stderr, "METAL_CB unavailable\n");
        return;
    }
    original_commit = (void *) method_setImplementation(method, (IMP) traced_commit);
    fprintf(stderr, "METAL_CB installed\n");
}

extern int32_t align_gpu_graph_compute(void *, int32_t, const void *, int64_t, void *);

static int32_t graph(void *owner, int32_t kind, const void *key, int64_t length, void *value) {
    fprintf(stderr, "METAL_GRAPH_BEGIN kind=%d time=%.9f\n", kind, now());
    int32_t status = align_gpu_graph_compute(owner, kind, key, length, value);
    fprintf(stderr, "METAL_GRAPH_END kind=%d time=%.9f status=%d\n", kind, now(), status);
    return status;
}

__attribute__((used)) static struct { const void *replacement, *original; } interpose_graph
    __attribute__((section("__DATA,__interpose"))) = {
        (const void *) &graph, (const void *) &align_gpu_graph_compute
    };
