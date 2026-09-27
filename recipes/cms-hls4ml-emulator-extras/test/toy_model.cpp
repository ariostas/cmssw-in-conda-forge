// A model in the shape of the CMS ones: it runs its input through an hls::stream and an
// ap_shift_reg, the two classes this package reimplements, and returns a running sum.
#include "emulator.h"

#include "ap_fixed.h"
#include "ap_shift_reg.h"
#include "hls_math.h"
#include "hls_stream.h"
#include "utils/x_hls_utils.h"

#include <any>
#include <array>

using value_t = ap_fixed<24, 12>;

class ToyModel : public hls4mlEmulator::Model {
  std::array<value_t, 4> input_;
  value_t result_;

public:
  void prepare_input(std::any input) override { input_ = *std::any_cast<std::array<value_t, 4>*>(input); }

  void predict() override {
    hls::stream<value_t> fifo("toy");
    for (auto x : input_)
      fifo.write(x);
    // a 2-deep delay line: the sum of what falls out of it is the first two inputs
    ap_shift_reg<value_t, 2> delay;
    result_ = 0;
    while (!fifo.empty())
      result_ += delay.shift(fifo.read());
    // the newest element is at address 0
    result_ += delay.read(0) * 100;
    result_ += hls::exp(value_t(0)) - hls::numeric_limits<value_t>::min() + hls::numeric_limits<value_t>::min();
  }

  void read_result(std::any result) override { *std::any_cast<value_t*>(result) = result_; }
};

extern "C" hls4mlEmulator::Model* create_model() { return new ToyModel; }
extern "C" void destroy_model(hls4mlEmulator::Model* m) { delete m; }
