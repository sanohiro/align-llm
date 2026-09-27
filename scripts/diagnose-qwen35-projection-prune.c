/* Independent diagnostic only: omit the final Q6_K projection in a decode graph. */
#include "ggml.h"
#include "ggml-backend.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#define INTERPOSE(replacement, original) \
 __attribute__((used)) static struct { const void *a; const void *b; } \
 interpose_##original __attribute__((section("__DATA,__interpose"))) = \
 {(const void *)(unsigned long)&replacement,(const void *)(unsigned long)&original}
static _Thread_local int current_kind=-1;
static uint64_t now_ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t); return (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec; }
static int projection(struct ggml_tensor *t) {
 return t && t->op==GGML_OP_MUL_MAT && (t->flags & GGML_TENSOR_FLAG_OUTPUT) &&
   t->src[0] && t->src[1] && t->src[0]->type==GGML_TYPE_Q6_K &&
   t->src[1]->type==GGML_TYPE_F32 && t->type==GGML_TYPE_F32 &&
   ggml_is_vector(t->src[1]) && ggml_is_vector(t) &&
   t->src[0]->ne[0]==t->src[1]->ne[0] && t->src[0]->ne[1]==t->ne[0];
}
extern int32_t align_gpu_graph_compute(void *, int32_t, const void *, int64_t, void *);
static int32_t diag_align(void *owner,int32_t kind,const void *key,int64_t length,void *value) {
 current_kind=kind;
 int32_t result=align_gpu_graph_compute(owner,kind,key,length,value);
 current_kind=-1;
 return result;
}
INTERPOSE(diag_align,align_gpu_graph_compute);
extern enum ggml_status ggml_backend_graph_compute(ggml_backend_t,struct ggml_cgraph *);
static enum ggml_status diag_backend(ggml_backend_t backend,struct ggml_cgraph *graph) {
 int n=ggml_graph_n_nodes(graph), index=-1;
 for(int i=0;i<n;i++) if(projection(ggml_graph_node(graph,i))) {if(index>=0)abort();index=i;}
 int enabled=getenv("ALIGN_Q35_PROJECTION_SKIP") && getenv("ALIGN_Q35_PROJECTION_SKIP")[0]=='1';
 struct ggml_context *ctx=NULL;
 struct ggml_cgraph *target=graph;
 if(current_kind==1 || current_kind==2) {
  if(index!=n-1) {fprintf(stderr,"Q35_PROJ_DIAG invalid-final index=%d nodes=%d\n",index,n);abort();}
  if(enabled) {
   struct ggml_init_params params={0};
   params.mem_size=ggml_graph_overhead_custom((size_t)n, false)+1024;
   params.no_alloc=true;
   ctx=ggml_init(params);
   if(!ctx) abort();
   target=ggml_new_graph_custom(ctx,(size_t)n,false);
   if(!target) abort();
   for(int i=0;i<n-1;i++)ggml_graph_add_node(target,ggml_graph_node(graph,i));
   if(ggml_graph_n_nodes(target)!=n-1)abort();
  }
 }
 uint64_t start=now_ns();
 enum ggml_status status=ggml_backend_graph_compute(backend,target);
 uint64_t elapsed=now_ns()-start;
 if(ctx)ggml_free(ctx);
 fprintf(stderr,"Q35_PROJ_DIAG kind=%d skip=%d projection_index=%d nodes=%d elapsed_ns=%llu status=%d\n",current_kind,enabled,index,n,(unsigned long long)elapsed,status);
 return status;
}
INTERPOSE(diag_backend,ggml_backend_graph_compute);
