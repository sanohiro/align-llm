#define main acquisition_main
#include "reference-acquire.cpp"
#undef main

int main() {
    float equal[] = {0, 0, 0, 0};
    Random first(42), other(7);
    assert(sample(equal, 4, true, first) == 3);
    assert(sample(equal, 4, true, first) == 1);
    assert(sample(equal, 4, true, other) == 0);
    assert(sample(equal, 4, false, first) == 0);
    float single[] = {-12};
    Random minimum(UINT64_C(0x8000000000000000)), maximum(UINT64_C(0x7fffffffffffffff));
    assert(sample(single, 1, true, minimum) == 0);
    assert(sample(single, 1, true, maximum) == 0);
    std::vector<float> min_p(21, -3.1f); min_p[0] = 0;
    Random limited(3);
    assert(sample(min_p.data(), int(min_p.size()), true, limited) == 0);
    assert(selected_name("l_out-27") && selected_name("ffn_moe_topk-15"));
    assert(!selected_name("l_out-") && !selected_name("l_out-0 (reshaped)") &&
        !selected_name("ffn_moe_probs-0/../../escape"));
    std::puts("Independent acquisition sampler/name owner: PASS");
}
