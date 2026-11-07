// SPDX-License-Identifier: MIT
package chromaapex
/*
#cgo CFLAGS: -I../../core/include
#include "chroma_apex.h"
*/
import "C"
import (
 "fmt"
 "unsafe"
)
// OrderFloat64 returns a stable permutation. NaNs sort last, signed zeros tie.
func OrderFloat64(keys []float64) ([]uint32,error) {
  out:=make([]uint32,len(keys));var s C.apx_stats
  if len(keys)==0{return out,nil}
  code:=C.apx_order_f64((*C.double)(unsafe.Pointer(&keys[0])),C.size_t(len(keys)),(*C.uint32_t)(unsafe.Pointer(&out[0])),&s)
  if code!=C.APX_OK{return nil,fmt.Errorf("apex status %d",int(code))};return out,nil
}
// OrderInt64 returns a stable permutation of signed integer keys.
func OrderInt64(keys []int64) ([]uint32,error) {
  out:=make([]uint32,len(keys));var s C.apx_stats
  if len(keys)==0{return out,nil}
  code:=C.apx_order_i64((*C.int64_t)(unsafe.Pointer(&keys[0])),C.size_t(len(keys)),(*C.uint32_t)(unsafe.Pointer(&out[0])),&s)
  if code!=C.APX_OK{return nil,fmt.Errorf("apex status %d",int(code))};return out,nil
}
