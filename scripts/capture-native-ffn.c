/* Independent macOS validation interposer. Retains activation lifetimes and
 * writes actual FFN weights/input/reference output for the first decode graph.
 * Never load this library during a timed campaign: retention changes allocation.
 * clang -dynamiclib -I GGML/ggml/include -L BUNDLE -lggml-base -lggml \
 *   scripts/capture-native-ffn.c -o capture-native-ffn.dylib
 * Set ALIGN_FFN_CAPTURE to an existing private output directory.
 */
#include "ggml.h"
#include "ggml-backend.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define INTERPOSE(replacement, original) \
    __attribute__((used)) static struct { const void *a; const void *b; } \
    interpose_##original __attribute__((section("__DATA,__interpose"))) = \
        { (const void *)&replacement, (const void *)&original }

static int ffn_node(const struct ggml_tensor *t) {
    return t->op == GGML_OP_GLU && ggml_get_glu_op(t) == GGML_GLU_OP_SWIGLU &&
        t->src[0] && t->src[1] && t->src[0]->op == GGML_OP_MUL_MAT &&
        t->src[1]->op == GGML_OP_MUL_MAT &&
        t->src[0]->src[1] == t->src[1]->src[1] && ggml_is_vector(t);
}
static void capture_expand(struct ggml_cgraph *graph, struct ggml_tensor *tensor) {
    ggml_build_forward_expand(graph, tensor);
    if (!getenv("ALIGN_FFN_CAPTURE")) return;
    for (int i = 0; i < ggml_graph_n_nodes(graph); ++i) {
        struct ggml_tensor *t = ggml_graph_node(graph, i);
        if (ffn_node(t)) {
            ggml_set_output(t->src[0]->src[1]);
            ggml_set_output(t);
        }
        if (t->op == GGML_OP_MUL_MAT && t->src[1] && ffn_node(t->src[1])) ggml_set_output(t);
    }
}
INTERPOSE(capture_expand, ggml_build_forward_expand);

static void save(const char *dir, int layer, const char *role, const struct ggml_tensor *t) {
    char path[4096];
    if (snprintf(path, sizeof(path), "%s/%02d-%s.bin", dir, layer, role) >= (int)sizeof(path)) abort();
    size_t size = ggml_nbytes(t);
    void *data = malloc(size);
    if (!data || !ggml_is_contiguous(t)) abort();
    ggml_backend_tensor_get(t, data, 0, size);
    FILE *file = fopen(path, "wb");
    if (!file || fwrite(data, 1, size, file) != size || fclose(file)) abort();
    free(data);
    fprintf(stderr, "FFN_CAPTURE layer=%d role=%s type=%d width=%lld rows=%lld bytes=%zu\n",
            layer, role, t->type, (long long)t->ne[0], (long long)t->ne[1], size);
}
static enum ggml_status capture_compute(ggml_backend_t backend, struct ggml_cgraph *graph) {
    enum ggml_status result = ggml_backend_graph_compute(backend, graph);
    static int captured = 0;
    const char *dir = getenv("ALIGN_FFN_CAPTURE");
    if (result != GGML_STATUS_SUCCESS || !dir || captured) return result;
    int layer = -1;
    for (int i = 0; i < ggml_graph_n_nodes(graph); ++i) {
        struct ggml_tensor *t = ggml_graph_node(graph, i);
        if (t->op == GGML_OP_MUL_MAT && t->src[1] && ffn_node(t->src[1])) {
            ++layer;
            struct ggml_tensor *glu = t->src[1];
            save(dir, layer, "gate", glu->src[0]->src[0]);
            save(dir, layer, "up", glu->src[1]->src[0]);
            save(dir, layer, "input", glu->src[0]->src[1]);
            save(dir, layer, "gated", glu);
            save(dir, layer, "down", t->src[0]);
            save(dir, layer, "output", t);
        }
    }
    if (layer >= 0) captured = 1;
    return result;
}
INTERPOSE(capture_compute, ggml_backend_graph_compute);
