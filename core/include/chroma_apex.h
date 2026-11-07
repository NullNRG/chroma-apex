/* SPDX-License-Identifier: MIT */
#ifndef CHROMA_APEX_H
#define CHROMA_APEX_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#if defined(_WIN32) && defined(CHROMA_APEX_BUILD)
# define APX_API __declspec(dllexport)
#elif defined(_WIN32)
# define APX_API __declspec(dllimport)
#else
# define APX_API
#endif
#define APX_VERSION_MAJOR 0
#define APX_VERSION_MINOR 1
#define APX_VERSION_PATCH 0
/* Every output index refers to the original input position. On success,
 * output contains a stable ascending permutation. Input is never changed.
 * Counts are size_t, indices are uint32_t, so n <= UINT32_MAX.
 * Floating point total-order: -infinity < finite < +infinity < NaN.
 * -0 and +0 compare equal; all NaNs compare equal. Stable ties preserve position.
 * out and keys must not alias. */
enum apx_status {
  APX_OK=0, APX_BAD_ARGUMENT=1, APX_TOO_LARGE=2,
  APX_NO_MEMORY=3
};
enum apx_path { APX_EMPTY=0, APX_ORDERED=1, APX_RADIX=2, APX_COUNTING=3, APX_REVERSED=4 };
typedef struct apx_stats {
  uint64_t count;
  uint32_t passes;
  uint32_t path;
  uint64_t scratch_bytes_peak; /* excludes caller-owned input/output */
} apx_stats;
APX_API int apx_order_f64(const double *keys, size_t n, uint32_t *out, apx_stats *stats);
APX_API int apx_order_u64(const uint64_t *keys, size_t n, uint32_t *out, apx_stats *stats);
APX_API int apx_order_i64(const int64_t *keys, size_t n, uint32_t *out, apx_stats *stats);
APX_API const char *apx_status_string(int status);
APX_API uint32_t apx_abi_version(void); /* (major<<16) | minor */
#ifdef __cplusplus
}
#endif
#endif
