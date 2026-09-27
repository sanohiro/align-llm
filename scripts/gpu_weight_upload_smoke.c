/* Transfer-policy owner; run both normally and with forced transfer failure. */
#include "ggml_shim_stub.c"
#include <assert.h>

int main(void) {
    assert(align_gpu_weight_upload_mode(NULL, 1) == ALIGN_GPU_CONFIG);
    for (int mode = 0; mode <= 1; ++mode) {
        struct align_gpu_device_state state = {0}, other = {0};
        unsigned char destination[32] = {0}, staging[8], source[16];
        memset(staging, 0x7b, sizeof(staging));
        for (int i = 0; i < 16; ++i) { source[i] = (unsigned char) (i + 1); }
        assert(align_gpu_weight_upload_mode(&state, mode) == ALIGN_GPU_CONFIG);
        state.memory_allocated = 1;
        state.staging_bytes = sizeof(staging);
        state.staging = staging;
        state.weights_buffer = destination;
        assert(align_gpu_weight_upload_mode(&state, -1) == ALIGN_GPU_CONFIG);
        assert(align_gpu_weight_upload_mode(&state, 2) == ALIGN_GPU_CONFIG);
        state.shape_planning = 1;
        assert(align_gpu_weight_upload_mode(&state, mode) == ALIGN_GPU_CONFIG);
        state.shape_planning = 0;
        assert(align_gpu_weight_upload_mode(&state, mode) == ALIGN_GPU_OK);
        assert(state.synchronous_weight_upload == mode);
        assert(other.synchronous_weight_upload == 0);
        state.weights_expected = state.weights_created = 1;
        state.pending_weight_offset = 8;
        state.pending_weight_bytes = sizeof(source);
        assert(align_gpu_weight_upload_mode(&state, 1 - mode) == ALIGN_GPU_CONFIG);
        assert(state.synchronous_weight_upload == mode);
        assert(align_gpu_weight_upload(&state, 0, 1, source, 8) == ALIGN_GPU_CONFIG);
        assert(align_gpu_weight_upload(&state, 0, 0, source, 9) == ALIGN_GPU_CONFIG);
        assert(align_gpu_weight_upload(&state, 1, 0, source, 8) == ALIGN_GPU_CONFIG);
        assert(align_gpu_weight_upload(&state, 0, 0, NULL, 8) == ALIGN_GPU_CONFIG);
        assert(state.weights_uploaded_bytes == 0);
        if (ALIGN_GPU_FORCE_TRANSFER_FAILURE) {
            assert(align_gpu_weight_upload(&state, 0, 0, source, 8) == ALIGN_GPU_TRANSFER);
            assert(state.weights_failed && state.weights_uploaded_bytes == 0);
            for (int i = 0; i < 32; ++i) { assert(destination[i] == 0); }
            for (int i = 0; i < 8; ++i) { assert(staging[i] == 0x7b); }
        } else {
            assert(align_gpu_weight_upload(&state, 0, 0, source, 8) == ALIGN_GPU_OK);
            assert(state.weights_uploaded == 0 && state.weights_uploaded_bytes == 8);
            assert(align_gpu_weight_upload(&state, 0, 8, source + 8, 8) == ALIGN_GPU_OK);
            assert(state.weights_uploaded == 1 && state.weights_uploaded_bytes == 16);
            assert(memcmp(destination + 8, source, 16) == 0);
            for (int i = 0; i < 8; ++i) {
                assert(destination[i] == 0 && destination[24 + i] == 0);
                assert(staging[i] == (mode ? 0x7b : source[8 + i]));
            }
            assert(align_gpu_weight_upload(&state, 0, 16, source, 1) == ALIGN_GPU_CONFIG);
        }
    }
    return 0;
}
