/* Native admission must include externally owned simultaneous capacity. */
static void host_reservation(void) {
    struct align_gpu_device_state state = {0};
    state.host_budget_bytes = 1000;
    state.device_budget_bytes = 1000;
    assert(align_gpu_host_reserve(NULL, 1) == ALIGN_GPU_CONFIG);
    assert(align_gpu_host_reserved(NULL) == -1);
    assert(align_gpu_host_reserve(&state, -1) == ALIGN_GPU_CONFIG);
    assert(align_gpu_host_reserve(&state, 1001) == ALIGN_GPU_MEMORY_BUDGET);
    assert(align_gpu_host_reserve(&state, 729) == ALIGN_GPU_OK);
    assert(align_gpu_memory_admit(&state, 128, 64, 512, 128, 128, 16) == ALIGN_GPU_MEMORY_BUDGET);
    assert(state.memory_planned == 0);
    assert(align_gpu_host_reserve(&state, 728) == ALIGN_GPU_OK);
    assert(align_gpu_memory_admit(&state, 128, 64, 512, 128, 128, 16) == ALIGN_GPU_OK);
    assert(align_gpu_memory_bytes(&state, 0) == 1000);
    assert(align_gpu_host_reserved(&state) == 728);
    assert(align_gpu_host_reserve(&state, 0) == ALIGN_GPU_CONFIG);
    assert(align_gpu_host_reserved(&state) == 728);
}
