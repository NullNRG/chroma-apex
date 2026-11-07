// SPDX-License-Identifier: MIT
//! Requires libchroma_apex built and available on the linker/runtime search path.
#[repr(C)]
#[derive(Default)]
struct ApexStats { count:u64, passes:u32, path:u32, scratch_bytes_peak:u64 }
#[link(name = "chroma_apex")]
extern "C" {
  fn apx_order_f64(keys:*const f64,n:usize,out:*mut u32,stats:*mut ApexStats)->i32;
}
pub fn order_f64(keys:&[f64])->Result<Vec<u32>,i32>{
  let mut out=vec![0u32;keys.len()];
  let mut stats=ApexStats::default();
  let err=unsafe { apx_order_f64(keys.as_ptr(),keys.len(),out.as_mut_ptr(),&mut stats) };
  if err!=0{Err(err)}else{Ok(out)}
}
