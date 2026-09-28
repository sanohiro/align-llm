// Shared diagnostic Metal kernel; not a product inference path.
#pragma once

static const char * kernel_source = R"METAL(
#include <metal_stdlib>
using namespace metal;

struct Q40Block { half scale; uchar packed[16]; };

inline float q40_dot(device const Q40Block * weight, float sum_x,
                     thread float * scaled_x, uint half_lane) {
    device const ushort * packed = (device const ushort *)weight->packed + half_lane * 4;
    float accum = 0.0f;
    for (uint i = 0; i < 4; ++i) {
        ushort q = packed[i];
        accum += scaled_x[i * 2] * float(q & 0x000f);
        accum += scaled_x[i * 2 + 1] * float(q & 0x0f00);
        accum += scaled_x[i * 2 + 8] * float(q & 0x00f0);
        accum += scaled_x[i * 2 + 9] * float(q & 0xf000);
    }
    return float(weight->scale) * (accum - 8.0f * sum_x);
}

kernel void q40_gate_up_swiglu(
    device const Q40Block * gate_weight [[buffer(0)]],
    device const Q40Block * up_weight [[buffer(1)]],
    device const float * input [[buffer(2)]],
    device float * gated [[buffer(3)]],
    uint tid [[thread_position_in_grid]]) {
    uint row = (tid / 32) * 4;
    if (row >= 6144) return;
    uint lane = tid % 32;
    uint block_lane = lane / 2;
    uint half_lane = lane % 2;
    float gate[4] = {0}, up[4] = {0};
    for (uint block = block_lane; block < 2048 / 32; block += 16) {
        float scaled_x[16], sum_x = 0.0f;
        uint at = block * 32 + half_lane * 8;
        for (uint i = 0; i < 8; i += 2) {
            float a = input[at + i], b = input[at + i + 1];
            float c = input[at + i + 16], d = input[at + i + 17];
            sum_x += a + b + c + d;
            scaled_x[i] = a;
            scaled_x[i + 1] = b / 256.0f;
            scaled_x[i + 8] = c / 16.0f;
            scaled_x[i + 9] = d / 4096.0f;
        }
        for (uint r = 0; r < 4; ++r) {
            gate[r] += q40_dot(gate_weight + (row + r) * (2048 / 32) + block,
                               sum_x, scaled_x, half_lane);
            up[r] += q40_dot(up_weight + (row + r) * (2048 / 32) + block,
                             sum_x, scaled_x, half_lane);
        }
    }
    for (uint r = 0; r < 4; ++r) {
        float g = simd_sum(gate[r]), u = simd_sum(up[r]);
        if (lane == 0) gated[row + r] = (g / (1.0f + exp(-g))) * u;
    }
}

kernel void q40_down(
    device const Q40Block * weights [[buffer(0)]],
    device const float * input [[buffer(1)]],
    device float * output [[buffer(2)]],
    uint tid [[thread_position_in_grid]]) {
    uint row = (tid / 32) * 4;
    if (row >= 2048) return;
    uint lane = tid % 32;
    uint block_lane = lane / 2;
    uint half_lane = lane % 2;
    float value[4] = {0};
    for (uint block = block_lane; block < 6144 / 32; block += 16) {
        float scaled_x[16], sum_x = 0.0f;
        uint at = block * 32 + half_lane * 8;
        for (uint i = 0; i < 8; i += 2) {
            float a = input[at + i], b = input[at + i + 1];
            float c = input[at + i + 16], d = input[at + i + 17];
            sum_x += a + b + c + d;
            scaled_x[i] = a;
            scaled_x[i + 1] = b / 256.0f;
            scaled_x[i + 8] = c / 16.0f;
            scaled_x[i + 9] = d / 4096.0f;
        }
        for (uint r = 0; r < 4; ++r) {
            value[r] += q40_dot(weights + (row + r) * (6144 / 32) + block,
                                sum_x, scaled_x, half_lane);
        }
    }
    for (uint r = 0; r < 4; ++r) {
        float total = simd_sum(value[r]);
        if (lane == 0) output[row + r] = total;
    }
}
)METAL";
