// Shared numerical kernel for the bounded screen and native runtime trial.
#pragma once

static const char *kTargetGreedyShader = R"metal(
#include <metal_stdlib>
using namespace metal;
struct Part { float value; uint index; uint invalid; };
kernel void partial(device const float *input [[buffer(0)]],
                    device Part *parts [[buffer(1)]],
                    constant uint &length [[buffer(2)]],
                    constant uint &groups [[buffer(3)]],
                    uint2 group [[threadgroup_position_in_grid]],
                    uint lane [[thread_index_in_threadgroup]]) {
    threadgroup float values[256];
    threadgroup uint indices[256];
    threadgroup uint invalids[256];
    const uint row = group.y;
    const uint tile = group.x;
    float best = -INFINITY;
    uint index = 0xffffffffu;
    uint invalid = 0;
    for (uint j = tile * 1024 + lane; j < min(length, (tile + 1) * 1024); j += 256) {
        float value = input[row * length + j];
        if (!isfinite(value)) invalid = 1;
        else if (value > best || (value == best && j < index)) {
            best = value;
            index = j;
        }
    }
    values[lane] = best;
    indices[lane] = index;
    invalids[lane] = invalid;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = 128; stride > 0; stride >>= 1) {
        if (lane < stride) {
            invalids[lane] |= invalids[lane + stride];
            float value = values[lane + stride];
            uint other = indices[lane + stride];
            if (value > values[lane] || (value == values[lane] && other < indices[lane])) {
                values[lane] = value;
                indices[lane] = other;
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (lane == 0) parts[row * groups + tile] = {values[0], indices[0], invalids[0]};
}
kernel void finish(device const Part *parts [[buffer(0)]],
                   device uint *result [[buffer(1)]],
                   constant uint &groups [[buffer(2)]],
                   uint row [[threadgroup_position_in_grid]],
                   uint lane [[thread_index_in_threadgroup]]) {
    threadgroup float values[256];
    threadgroup uint indices[256];
    threadgroup uint invalids[256];
    float best = -INFINITY;
    uint index = 0xffffffffu;
    uint invalid = 0;
    for (uint j = lane; j < groups; j += 256) {
        Part part = parts[row * groups + j];
        invalid |= part.invalid;
        if (part.value > best || (part.value == best && part.index < index)) {
            best = part.value;
            index = part.index;
        }
    }
    values[lane] = best;
    indices[lane] = index;
    invalids[lane] = invalid;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for (uint stride = 128; stride > 0; stride >>= 1) {
        if (lane < stride) {
            invalids[lane] |= invalids[lane + stride];
            float value = values[lane + stride];
            uint other = indices[lane + stride];
            if (value > values[lane] || (value == values[lane] && other < indices[lane])) {
                values[lane] = value;
                indices[lane] = other;
            }
        }
        threadgroup_barrier(mem_flags::mem_threadgroup);
    }
    if (lane == 0) result[row] = invalids[0] ? 0xffffffffu : indices[0];
}
)metal";
