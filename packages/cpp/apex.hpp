// SPDX-License-Identifier: MIT
#pragma once
#include "chroma_apex.h"
#include <vector>
#include <stdexcept>
#include <cstdint>
namespace chroma_apex {
inline std::vector<std::uint32_t> order(const std::vector<double>& keys){
  std::vector<std::uint32_t> out(keys.size());
  apx_stats s{};
  int code=apx_order_f64(keys.data(),keys.size(),out.data(),&s);
  if(code!=APX_OK)throw std::runtime_error(apx_status_string(code));
  return out;
}
}
