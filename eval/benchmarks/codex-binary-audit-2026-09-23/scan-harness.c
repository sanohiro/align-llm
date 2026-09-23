#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

struct view { const unsigned char *data; int64_t len; };
extern bool all_zero(const struct view *);

static void require(bool value) {
  if (!value) { fputs("scan validation failed\n", stderr); exit(1); }
}

static void validate(void) {
  size_t page = (size_t)sysconf(_SC_PAGESIZE);
  unsigned char *mem = mmap(NULL, page * 2, PROT_READ | PROT_WRITE,
                           MAP_ANON | MAP_PRIVATE, -1, 0);
  require(mem != MAP_FAILED);
  require(mprotect(mem + page, page, PROT_NONE) == 0);
  size_t cases = 0;
  for (size_t n = 0; n <= 256; ++n) {
    unsigned char *data = mem + page - n;
    memset(data, 0, n);
    struct view v = {data, (int64_t)n};
    require(all_zero(&v)); ++cases;
    for (size_t i = 0; i < n; ++i) {
      data[i] = (unsigned char)(1 + i % 255);
      require(!all_zero(&v)); ++cases;
      data[i] = 0;
    }
  }
  require(munmap(mem, page * 2) == 0);
  fprintf(stderr, "PASS: %zu zero/nonzero cases; inaccessible page immediately after each view\n", cases);
}

static uint64_t now_ns(void) {
  struct timespec t;
  require(clock_gettime(CLOCK_MONOTONIC, &t) == 0);
  return (uint64_t)t.tv_sec * 1000000000 + (uint64_t)t.tv_nsec;
}

int main(int argc, char **argv) {
  validate();
  if (argc == 2 && strcmp(argv[1], "check") == 0) return 0;
  const size_t size = 1048576;
  const int iterations = 2000;
  unsigned char *data = calloc(size, 1);
  require(data != NULL);
  struct view v = {data, (int64_t)size};
  volatile int observed = 0;
  for (int i = 0; i < 20; ++i) observed += all_zero(&v);
  uint64_t start = now_ns();
  for (int i = 0; i < iterations; ++i) observed += all_zero(&v);
  uint64_t elapsed = now_ns() - start;
  require(observed == iterations + 20);
  printf("{\"bytes\":%zu,\"iterations\":%d,\"elapsed_ns\":%llu,\"gb_per_s\":%.9f,\"observed\":%d}\n",
         size, iterations, (unsigned long long)elapsed,
         (double)size * iterations / (double)elapsed, observed);
  free(data);
  return 0;
}
