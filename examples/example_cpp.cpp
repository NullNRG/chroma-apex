// SPDX-License-Identifier: MIT
#include "apex.hpp"
#include <cassert>
#include <vector>
#include <iostream>
int main() {
  std::vector<double> values={5,2,5,1};
  auto p=chroma_apex::order(values);
  assert((p==std::vector<uint32_t>{3,1,0,2}));
  std::cout<<"PASS C++ binding\n";
}
