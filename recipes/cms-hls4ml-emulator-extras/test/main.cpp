#include "emulator.h"

#include "ap_fixed.h"

#include <array>
#include <cstdio>

int main() {
  using value_t = ap_fixed<24, 12>;
  // a name with a slash, so that dlopen() looks in the working directory
  hls4mlEmulator::ModelLoader loader("./ToyModel_v1");
  auto model = loader.load_model();
  std::array<value_t, 4> input{1.5, 2.25, 3, 4};
  value_t result;
  model->prepare_input(&input);
  model->predict();
  model->read_result(&result);
  // 1.5 + 2.25 shifted out, 4 newest in the register (x100), exp(0) = 1
  std::printf("result %g\n", result.to_double());
  return result == value_t(404.75) ? 0 : 1;
}
