// Local diagnostic: substitute the final Q4_0 FFN in a real decode graph.
// Fixed shape is deliberate for this probe and never enters product code.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-impl.h"
#include "ggml-backend-impl.h"
#include "ggml-metal-device.h"
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <unistd.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <mach/mach_time.h>

#include "native_metal_q40_full_ffn_kernel.h"

#define INTERPOSE(replacement, original) \
  __attribute__((used)) static struct { const void *a; const void *b; } \
  interpose_##original __attribute__((section("__DATA,__interpose"))) = \
    { (const void *)&replacement, (const void *)&original }

static id<MTLDevice> device;
static id<MTLCommandQueue> queue;
static id<MTLComputePipelineState> fused;
static id<MTLComputePipelineState> down_pipeline;
static void *weight_base, *work_base;
static size_t weight_size, work_size;
static id<MTLBuffer> weight_view, work_view;
static id<MTLBuffer> gated_scratch;
static uint64_t work_view_epoch = UINT64_MAX;
static ggml_backend_event_t producer_event, consumer_event;
static ggml_backend_t event_backend;
static id<MTLCommandBuffer> native_pending;
static uint64_t calls;
static uint64_t *shared_calls;
static uint64_t native_ns, prefix_ns, suffix_ns;

static uint64_t now_ns() {
  return clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
}

static bool initialize() {
  if (device) return fused && down_pipeline && queue;
  const char *counter_path = getenv("ALIGN_LLM_NATIVE_TAIL_COUNTER");
  if (counter_path) {
    int fd = open(counter_path, O_RDWR | O_CLOEXEC);
    struct stat st;
    if (fd < 0 || fstat(fd, &st) != 0 || st.st_size != sizeof(uint64_t)) {
      if (fd >= 0) close(fd);
      return false;
    }
    void *mapped = mmap(nullptr, sizeof(uint64_t), PROT_READ | PROT_WRITE,
                        MAP_SHARED, fd, 0);
    close(fd);
    if (mapped == MAP_FAILED) return false;
    shared_calls = (uint64_t *)mapped;
  }
  device = MTLCreateSystemDefaultDevice();
  if (!device) return false;
  NSError *error = nil;
  id<MTLLibrary> library = [device newLibraryWithSource:
      [NSString stringWithUTF8String:kernel_source] options:nil error:&error];
  if (!library) { fprintf(stderr, "NATIVE_TAIL library: %s\n", error.localizedDescription.UTF8String); return false; }
  fused = [device newComputePipelineStateWithFunction:
      [library newFunctionWithName:@"q40_gate_up_swiglu"] error:&error];
  down_pipeline = [device newComputePipelineStateWithFunction:
      [library newFunctionWithName:@"q40_down"] error:&error];
  queue = [device newCommandQueue];
  gated_scratch = [device newBufferWithLength:6144 * sizeof(float)
      options:MTLResourceStorageModeShared];
  return fused && down_pipeline && queue && fused.threadExecutionWidth == 32
      && down_pipeline.threadExecutionWidth == 32 && gated_scratch;
}

static bool wrapper(ggml_tensor *tensor, id<MTLBuffer> *out, NSUInteger *offset) {
  if (!tensor || !tensor->buffer || !tensor->data) return false;
  const char *direct = getenv("ALIGN_LLM_NATIVE_TAIL_DIRECT");
  if (direct && strcmp(direct, "1") == 0) {
    static bool (*shared)(ggml_metal_buffer_t);
    static struct ggml_metal_buffer_id (*get_id)(ggml_metal_buffer_t,const struct ggml_tensor *);
    if (!shared || !get_id) {
      const char *bundle = getenv("DYLD_LIBRARY_PATH");
      if (!bundle) return false;
      NSString *path = [NSString stringWithFormat:@"%s/libggml-metal.so", bundle];
      void *plugin = dlopen(path.UTF8String,RTLD_LAZY | RTLD_LOCAL);
      if (!plugin) { fprintf(stderr,"NATIVE_TAIL cannot load pinned Metal plugin: %s\n",dlerror()); return false; }
      shared = (bool (*)(ggml_metal_buffer_t))dlsym(plugin,"ggml_metal_buffer_is_shared");
      get_id = (struct ggml_metal_buffer_id (*)(ggml_metal_buffer_t,const struct ggml_tensor *))
          dlsym(plugin,"ggml_metal_buffer_get_id");
    }
    ggml_metal_buffer_t metal = (ggml_metal_buffer_t)tensor->buffer->context;
    if (!metal || !shared || !get_id || !shared(metal)) {
      fprintf(stderr,"NATIVE_TAIL direct symbols shared=%p get_id=%p metal=%p\n",
        (void *)shared,(void *)get_id,(void *)metal);
      return false;
    }
    struct ggml_metal_buffer_id borrowed = get_id(metal, tensor);
    *out = (__bridge id<MTLBuffer>)borrowed.metal;
    *offset = borrowed.offs;
    return *out != nil && *offset <= (*out).length
        && ggml_nbytes(tensor) <= (*out).length - *offset;
  }
  void *base = ggml_backend_buffer_get_base(tensor->buffer);
  size_t size = ggml_backend_buffer_get_size(tensor->buffer);
  size_t page = (size_t)getpagesize();
  if (!base || size == 0 || page == 0 || (uintptr_t)base % page
      || size > SIZE_MAX - (page - 1)) return false;
  size_t mapped = ((size + page - 1) / page) * page;
  if (mapped > device.maxBufferLength) return false;
  uintptr_t pos = (uintptr_t)tensor->data - (uintptr_t)base;
  if (pos > size || ggml_nbytes(tensor) > size - pos) return false;
  if (size > 100000000) {
    if (weight_base != base || weight_size != size) {
      weight_view = [device newBufferWithBytesNoCopy:base length:mapped
          options:MTLResourceStorageModeShared deallocator:^(void *, NSUInteger) {}];
      weight_base = base; weight_size = size;
    }
    *out = weight_view;
  } else {
    if (work_base != base || work_size != size || work_view_epoch != calls) {
      work_view = [device newBufferWithBytesNoCopy:base length:mapped
          options:MTLResourceStorageModeShared deallocator:^(void *, NSUInteger) {}];
      work_base = base; work_size = size;
      work_view_epoch = calls;
    }
    *out = work_view;
  }
  *offset = pos;
  return *out && (*out).contents == base;
}

static bool encode(ggml_tensor *gate, ggml_tensor *up,
                   ggml_tensor *down, bool async) {
  id<MTLBuffer> wg, wu, wd, x, z;
  NSUInteger wg_o, wu_o, wd_o, x_o, z_o;
  if (!wrapper(gate->src[0], &wg, &wg_o) || !wrapper(up->src[0], &wu, &wu_o)
      || !wrapper(down->src[0], &wd, &wd_o) || !wrapper(gate->src[1], &x, &x_o)
      || !wrapper(down, &z, &z_o)) return false;
  id<MTLCommandBuffer> cmd = [queue commandBuffer];
  if (!cmd) return false;
  if (async) {
    const char *bundle = getenv("DYLD_LIBRARY_PATH");
    if (!bundle) return false;
    NSString *path = [NSString stringWithFormat:@"%s/libggml-metal.so", bundle];
    void *plugin = dlopen(path.UTF8String,RTLD_LAZY | RTLD_LOCAL);
    auto wait_event = (void (*)(ggml_metal_event_t, ggml_metal_cmd_buf_t))
        dlsym(plugin,"ggml_metal_event_encode_wait");
    if (!wait_event) return false;
    wait_event((ggml_metal_event_t)producer_event->context,(__bridge void *)cmd);
  }
  id<MTLComputeCommandEncoder> encoder = [cmd computeCommandEncoder];
  if (!encoder) return false;
  [encoder setComputePipelineState:fused];
  [encoder setBuffer:wg offset:wg_o atIndex:0];
  [encoder setBuffer:wu offset:wu_o atIndex:1];
  [encoder setBuffer:x offset:x_o atIndex:2];
  [encoder setBuffer:gated_scratch offset:0 atIndex:3];
  [encoder dispatchThreads:MTLSizeMake(6144 / 4 * 32, 1, 1)
      threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
  [encoder memoryBarrierWithScope:MTLBarrierScopeBuffers];
  [encoder setComputePipelineState:down_pipeline];
  [encoder setBuffer:wd offset:wd_o atIndex:0];
  [encoder setBuffer:gated_scratch offset:0 atIndex:1];
  [encoder setBuffer:z offset:z_o atIndex:2];
  [encoder dispatchThreads:MTLSizeMake(2048 / 4 * 32, 1, 1)
      threadsPerThreadgroup:MTLSizeMake(128, 1, 1)];
  [encoder endEncoding];
  if (async) {
    const char *bundle = getenv("DYLD_LIBRARY_PATH");
    NSString *path = [NSString stringWithFormat:@"%s/libggml-metal.so", bundle];
    void *plugin = dlopen(path.UTF8String,RTLD_LAZY | RTLD_LOCAL);
    auto signal_event = (void (*)(ggml_metal_event_t, ggml_metal_cmd_buf_t))
        dlsym(plugin,"ggml_metal_event_encode_signal");
    if (!signal_event) return false;
    signal_event((ggml_metal_event_t)consumer_event->context,(__bridge void *)cmd);
  }
  [cmd commit];
  if (async) { native_pending = cmd; return true; }
  [cmd waitUntilCompleted];
  if (cmd.status != MTLCommandBufferStatusCompleted) {
    fprintf(stderr, "NATIVE_TAIL command failed: %s\n", cmd.error.localizedDescription.UTF8String);
    return false;
  }
  return true;
}

static enum ggml_status compute(ggml_backend_t backend, struct ggml_cgraph *graph) {
  const char *enabled = getenv("ALIGN_LLM_NATIVE_TAIL_DIAGNOSTIC");
  if (!enabled || strcmp(enabled, "1")) return ggml_backend_graph_compute(backend, graph);
  int n = ggml_graph_n_nodes(graph), glu = -1;
  for (int i = 2; i + 2 < n; ++i)
    if (ggml_graph_node(graph, i)->op == GGML_OP_GLU
        && ggml_graph_node(graph, i)->ne[1] == 1) glu = i;
  if (glu < 0 || n - glu > 16) return ggml_backend_graph_compute(backend, graph);
  ggml_tensor *gate = ggml_graph_node(graph, glu-2), *up = ggml_graph_node(graph, glu-1);
  ggml_tensor *gated = ggml_graph_node(graph, glu), *down = ggml_graph_node(graph, glu+1);
  if (gate->op != GGML_OP_MUL_MAT || up->op != GGML_OP_MUL_MAT
      || gated->op != GGML_OP_GLU || down->op != GGML_OP_MUL_MAT
      || gate->ne[0] != 6144 || down->ne[0] != 2048
      || gate->src[0]->type != GGML_TYPE_Q4_0
      || up->src[0]->type != GGML_TYPE_Q4_0
      || down->src[0]->type != GGML_TYPE_Q4_0
      || !initialize()) return ggml_backend_graph_compute(backend, graph);
  const char *async_setting = getenv("ALIGN_LLM_NATIVE_TAIL_ASYNC");
  bool async = async_setting && strcmp(async_setting,"1") == 0;
  if (async && event_backend != backend) {
    if (producer_event) ggml_backend_event_free(producer_event);
    if (consumer_event) ggml_backend_event_free(consumer_event);
    producer_event = ggml_backend_event_new(ggml_backend_get_device(backend));
    consumer_event = ggml_backend_event_new(ggml_backend_get_device(backend));
    if (!producer_event || !consumer_event) abort();
    event_backend = backend;
  }
  if (calls < 4) fprintf(stderr,
      "NATIVE_TAIL layout call=%llu x=%p ux=%p gated=%p down=%p gate=%p up=%p add0=%p add1=%p graph=%p\n",
      (unsigned long long)calls, gate->src[1]->data, up->src[1]->data, gated->data, down->data,
      gate->data, up->data, ggml_graph_node(graph, glu+2)->src[0]->data,
      ggml_graph_node(graph, glu+2)->src[1]->data, (void *)graph);
  struct ggml_cgraph prefix = ggml_graph_view(graph, 0, glu-2);
  struct ggml_cgraph suffix = ggml_graph_view(graph, glu+2, n);
  uint64_t start = now_ns();
  enum ggml_status status = async ? ggml_backend_graph_compute_async(backend, &prefix)
                                  : ggml_backend_graph_compute(backend, &prefix);
  prefix_ns += now_ns() - start;
  if (status != GGML_STATUS_SUCCESS) return status;
  if (async) ggml_backend_event_record(producer_event, backend);
  std::vector<float> before;
  if (!async && calls < 3) {
    before.resize(2048);
    ggml_backend_tensor_get(gate->src[1], before.data(), 0, 8192);
    fprintf(stderr, "NATIVE_TAIL input call=%llu first=%g,%g,%g,%g ptr=%g,%g\n",
      (unsigned long long)calls, before[0], before[1], before[2], before[3],
      ((float *)gate->src[1]->data)[0], ((float *)gate->src[1]->data)[1]);
  }
  start = now_ns();
  if (!encode(gate, up, down, async)) {
    fprintf(stderr, "NATIVE_TAIL encode rejected admitted graph buffers\n");
    abort();
  }
  native_ns += now_ns() - start;
  if (async) ggml_backend_event_wait(backend, consumer_event);
  if (!before.empty()) {
    std::vector<float> after(2048);
    ggml_backend_tensor_get(gate->src[1], after.data(), 0, 8192);
    float worst=0;
    for (int i=0;i<2048;++i) worst=fmaxf(worst,fabsf(before[i]-after[i]));
    fprintf(stderr,"NATIVE_TAIL source_modified call=%llu max_abs=%g\n",
      (unsigned long long)calls,worst);
  }
  const char *shadow = getenv("ALIGN_LLM_NATIVE_TAIL_SHADOW");
  if (async && shadow && strcmp(shadow,"1") == 0) abort();
  if (shadow && strcmp(shadow, "1") == 0) {
    std::vector<float> actual(2048), reference(2048), source(2048), gated_ref(6144);
    ggml_backend_tensor_get(gate->src[1], source.data(), 0, 8192);
    ggml_backend_tensor_get(down, actual.data(), 0, 8192);
    struct ggml_cgraph ffn = ggml_graph_view(graph, glu-2, glu+2);
    status = ggml_backend_graph_compute(backend, &ffn);
    if (status != GGML_STATUS_SUCCESS) return status;
    ggml_backend_tensor_get(gated, gated_ref.data(), 0, gated_ref.size() * sizeof(float));
    float gated_worst = 0;
    const float *gated_actual = (const float *)gated_scratch.contents;
    for (int i=0;i<6144;++i) gated_worst=fmaxf(gated_worst,fabsf(gated_actual[i]-gated_ref[i]));
    fprintf(stderr,"NATIVE_TAIL gated_diff=%g gated0=%g ref0=%g\n",
      gated_worst,gated_actual[0],gated_ref[0]);
    ggml_backend_tensor_get(down, reference.data(), 0, 8192);
    float max_diff = 0;
    for (int i = 0; i < 2048; ++i) {
      float diff = fabsf(actual[i]-reference[i]);
      if (!std::isfinite(actual[i]) || !std::isfinite(reference[i])
          || diff > 0.005f + 0.0005f * fabsf(reference[i])) {
        fprintf(stderr, "NATIVE_TAIL mismatch index=%d actual=%g reference=%g\n",
          i, actual[i], reference[i]); abort();
      }
      if (diff > max_diff) max_diff = diff;
    }
    ggml_backend_tensor_set(gate->src[1], source.data(), 0, 8192);
    ggml_backend_tensor_set(down, actual.data(), 0, 8192);
    fprintf(stderr, "NATIVE_TAIL shadow max_abs=%g\n", max_diff);
  }
  start = now_ns();
  status = async ? ggml_backend_graph_compute_async(backend, &suffix)
                 : ggml_backend_graph_compute(backend, &suffix);
  if (async) {
    ggml_backend_synchronize(backend);
    [native_pending waitUntilCompleted];
    if (native_pending.status != MTLCommandBufferStatusCompleted) abort();
    native_pending = nil;
  }
  suffix_ns += now_ns() - start;
  ++calls;
  if (shared_calls) __atomic_store_n(shared_calls, calls, __ATOMIC_RELEASE);
  if (calls == 1 || calls % 32 == 0)
    fprintf(stderr, "NATIVE_TAIL calls=%llu prefix_ms=%.3f native_ms=%.3f suffix_ms=%.3f\n",
      (unsigned long long)calls, prefix_ns / 1e6, native_ns / 1e6, suffix_ns / 1e6);
  return status;
}
INTERPOSE(compute, ggml_backend_graph_compute);
