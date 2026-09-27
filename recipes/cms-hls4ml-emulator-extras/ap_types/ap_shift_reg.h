// SPDX-License-Identifier: Apache-2.0
//
// ap_shift_reg for C simulation, written for conda-forge to replace the Xilinx header of the
// same name that hls4mlEmulatorExtras bundles, which is not under an open licence. It
// implements the interface the Vivado/Vitis HLS documentation describes: a shift register of
// N elements, where element 0 is the newest and element N-1 the oldest.
#ifndef HLS4ML_EMULATOR_AP_SHIFT_REG_H
#define HLS4ML_EMULATOR_AP_SHIFT_REG_H

#include <cassert>

template <typename T, unsigned int N>
class ap_shift_reg {
public:
  ap_shift_reg() : mem_() {}
  explicit ap_shift_reg(const char*) : mem_() {}

  // Returns the element at `addr` as it was before the call, then, if `en`, shifts every
  // element one place towards the end (dropping the oldest) and puts `din` at the front. With
  // the default address this reads the element that the shift pushes out.
  T shift(T din, unsigned int addr = N - 1, bool en = true) {
    assert(addr < N);
    T out = mem_[addr];
    if (en) {
      for (unsigned int i = N - 1; i > 0; --i)
        mem_[i] = mem_[i - 1];
      mem_[0] = din;
    }
    return out;
  }

  T read(unsigned int addr = N - 1) const {
    assert(addr < N);
    return mem_[addr];
  }

private:
  T mem_[N];
};

#endif
