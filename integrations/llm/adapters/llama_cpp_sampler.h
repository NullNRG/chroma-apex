/* SPDX-License-Identifier: MIT */
#ifndef APEX_LLAMA_CPP_SAMPLER_H
#define APEX_LLAMA_CPP_SAMPLER_H
#include "llama.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Chain after repeat/grammar masks and instead of the normal
 * top_k+top_p+temperature+distribution samplers.
 * Not suitable for arbitrary non-standard postprocessors or GPU-resident
 * candidate arrays without transfer.
 */
llama_sampler * llama_sampler_init_chroma_apex(
    int32_t top_k,float top_p,float temperature,uint32_t seed);
#ifdef __cplusplus
}
#endif
#endif
