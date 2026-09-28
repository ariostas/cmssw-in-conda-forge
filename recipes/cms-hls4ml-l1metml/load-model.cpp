// Loads a model library the way CMSSW does, by bare name through the emulator interface, and
// creates and destroys a model. What a model's inputs are is up to the CMSSW code using it.
#include "emulator.h"

#include <cstdio>

int main(int argc, char** argv) {
  if (argc != 2)
    return 2;
  hls4mlEmulator::ModelLoader loader(argv[1]);
  auto model = loader.load_model();
  std::printf("%s: %s\n", argv[1], model ? "loaded" : "not loaded");
  return model ? 0 : 1;
}
