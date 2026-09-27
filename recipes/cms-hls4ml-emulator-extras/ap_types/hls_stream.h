// SPDX-License-Identifier: Apache-2.0
//
// hls::stream for C simulation, written for conda-forge to replace the Xilinx header of the
// same name that hls4mlEmulatorExtras bundles, which is not under an open licence. It
// implements the interface the Vivado/Vitis HLS documentation describes: a FIFO between two
// functions, which in software is simply an unbounded queue.
#ifndef HLS4ML_EMULATOR_HLS_STREAM_H
#define HLS4ML_EMULATOR_HLS_STREAM_H

#include <cstddef>
#include <deque>
#include <iostream>
#include <string>
#include <utility>

namespace hls {

  template <typename T>
  class stream {
  public:
    stream() = default;
    explicit stream(const char* name) : name_(name) {}
    explicit stream(const std::string& name) : name_(name) {}

    // a stream is a hardware channel: it cannot be copied
    stream(const stream&) = delete;
    stream& operator=(const stream&) = delete;

    bool empty() const { return data_.empty(); }
    // there is no depth in simulation, so a stream is never full
    bool full() const { return false; }
    std::size_t size() const { return data_.size(); }

    // Blocking read. In hardware a read from an empty stream would wait forever; in
    // simulation it is a bug in the design, reported here, and gives a default value.
    T read() {
      if (data_.empty()) {
        std::cerr << "WARNING: hls::stream '" << name_ << "' is read while empty" << std::endl;
        return T();
      }
      T head = std::move(data_.front());
      data_.pop_front();
      return head;
    }
    void read(T& head) { head = read(); }
    void operator>>(T& head) { read(head); }

    // non-blocking read: false, and `head` unchanged, if there is nothing to read
    bool read_nb(T& head) {
      if (data_.empty())
        return false;
      head = read();
      return true;
    }

    void write(const T& tail) { data_.push_back(tail); }
    void operator<<(const T& tail) { write(tail); }
    bool write_nb(const T& tail) {
      write(tail);
      return true;
    }

  private:
    std::string name_;
    std::deque<T> data_;
  };

}  // namespace hls

#endif
