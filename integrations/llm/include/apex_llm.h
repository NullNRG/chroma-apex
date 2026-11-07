/* SPDX-License-Identifier: MIT */
#ifndef APEX_LLM_H
#define APEX_LLM_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* No library RNG: callers supply uniform u in [0,1) to preserve their own seed streams.
 * Non-finite NaN/-infinity logits are masked. Positive infinity forms a uniform
 * distribution over only the +infinity entries. Equal logits break ties by token ID.
 * top_k=0 means entire vocabulary; temperature=0 means greedy; top_p in (0,1].
 */
typedef struct apx_llm_stats {
  uint32_t candidate_count;
  uint32_t retained_count;
  uint32_t strategy; /* 1 greedy, 2 small heap, 3 selection, 4 radix, 5 partial_sort, 6 nth_element */
} apx_llm_stats;
/* strategy=0 automatic APEX; 1 full comparison sort (reference);
 * 2 standard partial_sort; 3 standard nth_element + sort (top-k).
 * Every return code !=0 is a failure, output is not valid on failure. */
int apx_llm_sample(const float *logits, uint32_t n, float temperature,
                   uint32_t top_k, float top_p, double uniform_01,
                   uint32_t *out_token, apx_llm_stats *stats, int strategy);
const char *apx_llm_status(int status);
#ifdef __cplusplus
}
#endif
#endif
