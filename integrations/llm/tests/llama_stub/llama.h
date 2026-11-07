#pragma once
#include <cstdint>
#include <cstddef>
using llama_token=int32_t;
struct llama_token_data{llama_token id;float logit;float p;};
struct llama_token_data_array{llama_token_data *data;size_t size;int64_t selected;bool sorted;};
struct llama_sampler;
struct llama_sampler_i {
 const char*(*name)(const llama_sampler*);
 void(*accept)(llama_sampler*,llama_token);
 void(*apply)(llama_sampler*,llama_token_data_array*);
 void(*reset)(llama_sampler*);
 llama_sampler*(*clone)(const llama_sampler*);
 void(*free)(llama_sampler*);
 void*backend_init;void*backend_accept;void*backend_apply;void*backend_set_input;
 void*backend_reset;void*copy_state;
};
struct llama_sampler{llama_sampler_i*iface;void*ctx;};
extern "C" llama_sampler* llama_sampler_init(llama_sampler_i*,void*);
