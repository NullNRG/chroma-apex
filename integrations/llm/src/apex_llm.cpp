/* SPDX-License-Identifier: MIT
 * Drop-in native CPU logits selector for autoregressive language models.
 * Unlike a full record sort, this path avoids ordering irrelevant tail tokens.
 */
#include "apex_llm.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <new>
#include <queue>
#include <vector>

namespace {
struct Candidate { uint32_t id; float value; uint32_t key; };
static uint32_t ordkey(float v) {
    // NaN is masked. Negative and positive zero compare equal.
    if (v == 0.0f) v = 0.0f;
    uint32_t b;
    std::memcpy(&b, &v, 4);
    uint32_t asc = (b & 0x80000000u) ? ~b : (b ^ 0x80000000u);
    return ~asc; // unsigned ascending produces floating descending
}
static bool better(const Candidate & a, const Candidate & b) {
    if (a.key != b.key) return a.key < b.key;
    return a.id < b.id;
}
static std::vector<Candidate> full_radix(std::vector<Candidate> a) {
    std::vector<Candidate> b(a.size());
    uint32_t v0 = a.front().key, diff = 0;
    for (const auto & c : a) diff |= c.key ^ v0;
    for (int shift = 0; shift < 32; shift += 8) {
        if (((diff >> shift) & 255u) == 0) continue;
        uint32_t counts[256] = {};
        for (const auto & c : a) counts[(c.key >> shift) & 255u]++;
        uint32_t sum = 0;
        for (uint32_t & count : counts) { uint32_t next = sum + count; count = sum; sum = next; }
        for (const auto & c : a) b[counts[(c.key >> shift) & 255u]++] = c;
        a.swap(b);
    }
    return a;
}
static std::vector<Candidate> small_heap(const std::vector<Candidate>& a, size_t k) {
    // priority_queue top is WORST retained token because `better` means <.
    std::priority_queue<Candidate, std::vector<Candidate>, decltype(&better)> heap(&better);
    for (const auto & c : a) {
        if (heap.size() < k) heap.push(c);
        else if (better(c, heap.top())) { heap.pop(); heap.push(c); }
    }
    std::vector<Candidate> selected;
    selected.reserve(k);
    while (!heap.empty()) { selected.push_back(heap.top()); heap.pop(); }
    std::sort(selected.begin(), selected.end(), better);
    return selected;
}
static std::vector<Candidate> prefix_select(const std::vector<Candidate>& a, size_t k) {
    // Four histogram probes determine the k-th 32-bit key without sorting the tail.
    uint32_t prefix = 0;
    uint32_t mask = 0;
    size_t rank = k;
    for (int shift = 24; shift >= 0; shift -= 8) {
        uint32_t counts[256] = {};
        for (const auto& c : a) if ((c.key & mask) == prefix) counts[(c.key >> shift) & 255u]++;
        uint32_t bucket = 0;
        for (; bucket < 255; ++bucket) {
            if (rank <= counts[bucket]) break;
            rank -= counts[bucket];
        }
        mask |= (0xffu << shift);
        prefix |= (bucket << shift);
    }
    std::vector<Candidate> selected;
    selected.reserve(k + 32);
    for (const auto & c : a) if (c.key <= prefix) selected.push_back(c);
    std::sort(selected.begin(), selected.end(), better);
    if (selected.size() > k) selected.resize(k); // keeps lowest IDs on exact ties
    return selected;
}
}

static int apx_llm_sample_impl(const float* logits, uint32_t n, float temperature,
    uint32_t top_k, float top_p, double u, uint32_t *out, apx_llm_stats *stats, int strategy) {
    if (stats) *stats = {};
    if (!logits || !out || !n || !std::isfinite(temperature) || temperature < 0 ||
        !(top_p > 0 && top_p <= 1) || !std::isfinite(u) || u < 0 || u >= 1 ||
        (strategy < 0 || strategy > 3)) return 1;
    // Greedy path: no candidate allocation, key packing, or sorting.
    if (temperature == 0.0f || top_k == 1) {
        bool any=false; float best=-std::numeric_limits<float>::infinity();
        uint32_t bestid=0, count=0;
        for(uint32_t i=0;i<n;i++) {
            const float x=logits[i];
            if(std::isnan(x)||x==-std::numeric_limits<float>::infinity())continue;
            ++count;
            if(!any || x>best) { best=x;bestid=i;any=true; }
        }
        if(!any)return 2;
        *out=bestid;
        if(stats){stats->candidate_count=count;stats->strategy=1;stats->retained_count=1;}
        return 0;
    }
    // For the usual top-40 at large vocab sizes, don't materialize the tail.
    if (strategy==0 && top_k>1 && top_k<=128 && n>=16384) {
        std::priority_queue<Candidate,std::vector<Candidate>,decltype(&better)> heap(&better);
        uint32_t count=0;
        bool has_positive_inf=false;
        for(uint32_t i=0;i<n;i++) {
            float x=logits[i];
            if(std::isnan(x)||x==-std::numeric_limits<float>::infinity())continue;
            ++count;
            if(x==std::numeric_limits<float>::infinity())has_positive_inf=true;
            Candidate c{i,x,ordkey(x)};
            if(heap.size()<top_k)heap.push(c);
            else if(better(c,heap.top())){heap.pop();heap.push(c);}
        }
        if(!count)return 2;
        std::vector<Candidate> candidates;
        candidates.reserve(heap.size());
        while(!heap.empty()){candidates.push_back(heap.top());heap.pop();}
        if(has_positive_inf){
            candidates.erase(std::remove_if(candidates.begin(),candidates.end(),
                [](const Candidate&c){return c.value!=std::numeric_limits<float>::infinity();}), candidates.end());
        }
        std::sort(candidates.begin(),candidates.end(),better);
        if(stats){stats->candidate_count=count;stats->strategy=2;}
        const double maxval=candidates[0].value;
        std::vector<double> weights(candidates.size());
        double sum=0;
        for(size_t i=0;i<candidates.size();i++) {
            weights[i]=has_positive_inf?1.0:std::exp((double(candidates[i].value)-maxval)/temperature);
            sum+=weights[i];
        }
        double mass=0;size_t keep=0;
        for(size_t i=0;i<weights.size();i++){mass+=weights[i];keep=i+1;if(mass>=sum*top_p)break;}
        if(stats)stats->retained_count=(uint32_t)keep;
        double target=u*mass, cumulative=0;
        for(size_t i=0;i<keep;i++){cumulative+=weights[i];if(target<cumulative){*out=candidates[i].id;return 0;}}
        *out=candidates[keep-1].id;return 0;
    }
    std::vector<Candidate> a;
    a.reserve(n);
    uint32_t bestid = 0;
    float best = -std::numeric_limits<float>::infinity();
    bool hasbest = false, has_inf = false;
    for (uint32_t i = 0; i < n; ++i) {
        float x = logits[i];
        if (std::isnan(x) || x == -std::numeric_limits<float>::infinity()) continue;
        if (!hasbest || x > best) { best=x; bestid=i; hasbest=true; }
        if (x == std::numeric_limits<float>::infinity()) has_inf = true;
        a.push_back({i, x, ordkey(x)});
    }
    if (!hasbest) return 2;
    if (stats) stats->candidate_count = (uint32_t)a.size();
    if (temperature == 0.0f || top_k == 1) {
        *out = bestid;
        if (stats) { stats->strategy=1; stats->retained_count=1; }
        return 0;
    }
    // +infinity logits: softmax is uniform over these tokens, not NaN.
    if (has_inf) {
        std::vector<Candidate> inf;
        inf.reserve(a.size());
        for (const auto & c : a) if (std::isinf(c.value) && c.value > 0) inf.push_back(c);
        a.swap(inf);
    }
    const size_t k = (top_k == 0) ? a.size() : std::min(size_t(top_k), a.size());
    std::vector<Candidate> selected;
    uint32_t used = 4;
    if (strategy == 1) {
        selected = a;
        std::sort(selected.begin(), selected.end(), better);
        selected.resize(k);
        used = 4;
    } else if (strategy == 2) {
        selected = a;
        std::partial_sort(selected.begin(), selected.begin()+k, selected.end(), better);
        selected.resize(k); used=5;
    } else if (strategy == 3) {
        selected = a;
        if (k < selected.size()) std::nth_element(selected.begin(), selected.begin()+k, selected.end(), better);
        selected.resize(k);
        std::sort(selected.begin(),selected.end(),better); used=6;
    } else if (k <= 128 && k < a.size() && n<16384) {
        selected=a;
        std::partial_sort(selected.begin(),selected.begin()+k,selected.end(),better);
        selected.resize(k);used=5;
    } else if (k <= 128 && k < a.size()) {
        selected = small_heap(a, k); used = 2;
    } else if (n<16384 && k<a.size()/2) {
        selected=a;
        std::nth_element(selected.begin(),selected.begin()+k,selected.end(),better);
        selected.resize(k);std::sort(selected.begin(),selected.end(),better);used=6;
    } else if (k < a.size()/2 && k < 8192) {
        selected = prefix_select(a, k); used = 3;
    } else {
        selected = full_radix(std::move(a));
        selected.resize(k); used = 4;
    }
    if (stats) stats->strategy = used;
    // Stable double-precision softmax; top-p is applied after top-k normalization.
    const double maxval = selected[0].value;
    std::vector<double> expv(selected.size());
    double total = 0.0;
    for (size_t i = 0; i < selected.size(); ++i) {
        expv[i] = has_inf ? 1.0 : std::exp((double(selected[i].value) - maxval)/temperature);
        total += expv[i];
    }
    double cumulative = 0;
    size_t keep = 0;
    for (size_t i = 0; i < selected.size(); ++i) {
        cumulative += expv[i];
        keep = i+1;
        if (cumulative >= total * (double)top_p) break;
    }
    if (stats) stats->retained_count = (uint32_t)keep;
    const double target = u * cumulative;
    double running = 0;
    for (size_t i = 0; i < keep; ++i) {
        running += expv[i];
        if (target < running) { *out = selected[i].id; return 0; }
    }
    *out = selected[keep-1].id;
    return 0;
}
extern "C" int apx_llm_sample(const float* logits, uint32_t n, float temperature,
    uint32_t top_k, float top_p, double u, uint32_t *out,
    apx_llm_stats *stats, int strategy) {
    try {return apx_llm_sample_impl(logits,n,temperature,top_k,top_p,u,out,stats,strategy);}
    catch(const std::bad_alloc&) {return 3;}
    catch(...) {return 4;}
}
extern "C" const char* apx_llm_status(int code) {
    switch(code) { case 0: return "ok"; case 1: return "invalid argument";
                   case 2: return "all logits masked"; case 3: return "out of memory";
                   case 4: return "native exception"; default: return "unknown"; }
}
