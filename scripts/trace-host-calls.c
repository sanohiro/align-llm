// Independent macOS dyld interposer for allocation/copy call diagnostics.
// Build: clang -O2 -fno-builtin -dynamiclib -undefined dynamic_lookup \
//   scripts/trace-host-calls.c -o trace.dylib
// DYLD_INSERT_LIBRARIES selects it only for a diagnostic process. Counts cover
// intercepted symbols, not inlined operations, resident memory or physical GPU
// traffic. Suppress observation while printing; concurrent calls during that
// interval are omitted. Never use the instrumented elapsed time as a speed claim.
// A process-wide atomic guard avoids recursively allocating thread-local storage
// from inside the allocator hooks at process/thread initialization.
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <stdatomic.h>
#define IP(r,o) __attribute__((used)) static struct {const void *a,*b;} ip_##o __attribute__((section("__DATA,__interpose")))={(const void*)&r,(const void*)&o}
static _Atomic unsigned long long calls[6], bytes[6];
static _Atomic int paused;
static uint64_t ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static void bump(int k,size_t n){if(!paused){atomic_fetch_add(&calls[k],1);atomic_fetch_add(&bytes[k],n);}}
static void *m(size_t n){void *p=malloc(n);bump(0,n);return p;} IP(m,malloc);
static void *c(size_t n,size_t s){void *p=calloc(n,s);bump(1,n*s);return p;} IP(c,calloc);
static void *r(void *p,size_t n){void *q=realloc(p,n);bump(2,n);return q;} IP(r,realloc);
static void *cp(void *d,const void*s,size_t n){void *p=memcpy(d,s,n);bump(3,n);return p;} IP(cp,memcpy);
static void *mv(void *d,const void*s,size_t n){void *p=memmove(d,s,n);bump(4,n);return p;} IP(mv,memmove);
static void *st(void *d,int v,size_t n){void *p=memset(d,v,n);bump(5,n);return p;} IP(st,memset);
static void bz(void *d,size_t n){bzero(d,n);bump(5,n);} IP(bz,bzero);
static void report(const char *tag,int kind,uint64_t elapsed){
 paused++;
 unsigned long long c[6],b[6];for(int i=0;i<6;i++){c[i]=atomic_exchange(&calls[i],0);b[i]=atomic_exchange(&bytes[i],0);}
 fprintf(stderr,"HOST_COST tag=%s kind=%d ns=%llu malloc=%llu/%llu calloc=%llu/%llu realloc=%llu/%llu memcpy=%llu/%llu memmove=%llu/%llu memset=%llu/%llu\n",tag,kind,(unsigned long long)elapsed,c[0],b[0],c[1],b[1],c[2],b[2],c[3],b[3],c[4],b[4],c[5],b[5]);
 paused--;
}
static ssize_t rd(int fd,void *buf,size_t n){ssize_t v=read(fd,buf,n);if(fd==0&&v>0)report("input",(int)v,0);return v;} IP(rd,read);
static ssize_t wr(int fd,const void *buf,size_t n){if(fd==1)report("output",(int)n,0);return write(fd,buf,n);} IP(wr,write);
extern int32_t align_gpu_graph_compute(void*,int32_t,const void*,int64_t,void*);
static int32_t gc(void*o,int32_t k,const void*key,int64_t n,void*g){report("before_graph",k,0);uint64_t t=ns();int32_t v=align_gpu_graph_compute(o,k,key,n,g);report("after_graph",k,ns()-t);return v;}IP(gc,align_gpu_graph_compute);
extern int ggml_backend_graph_compute(void*,void*);
static int bc(void*b,void*g){uint64_t t=ns();int v=ggml_backend_graph_compute(b,g);paused++;fprintf(stderr,"HOST_BACKEND ns=%llu\n",(unsigned long long)(ns()-t));paused--;return v;}IP(bc,ggml_backend_graph_compute);
extern void ggml_backend_tensor_get(const void*,void*,size_t,size_t);
static void gt(const void*t,void*d,size_t o,size_t n){report("before_get",(int)n,0);uint64_t start=ns();ggml_backend_tensor_get(t,d,o,n);report("after_get",(int)n,ns()-start);}IP(gt,ggml_backend_tensor_get);
extern void ggml_backend_tensor_set(void*,const void*,size_t,size_t);
static void ts(void*t,const void*d,size_t o,size_t n){uint64_t start=ns();ggml_backend_tensor_set(t,d,o,n);paused++;fprintf(stderr,"HOST_SET bytes=%zu ns=%llu\n",n,(unsigned long long)(ns()-start));paused--;}IP(ts,ggml_backend_tensor_set);
extern void ggml_backend_synchronize(void*);
static void sy(void*b){uint64_t start=ns();ggml_backend_synchronize(b);paused++;fprintf(stderr,"HOST_SYNC ns=%llu\n",(unsigned long long)(ns()-start));paused--;}IP(sy,ggml_backend_synchronize);
