# Sourced by cmssw-build-layer in the developer area's src/ before building.

# DQMServices/Core commits the C++ that protoc 3.21 generated from ROOTFilePB.proto, and
# generated protobuf code only compiles against the runtime of the protoc that wrote it
# (its header #errors out otherwise). conda-forge's libprotobuf is far newer, so the code is
# generated again with the protoc that matches it, and put back where CMSSW keeps it.
(
  cd DQMServices/Core/src
  protoc --cpp_out=. ROOTFilePB.proto
  mv ROOTFilePB.pb.h ../interface/ROOTFilePB.pb.h
  sed -i 's|#include "ROOTFilePB.pb.h"|#include "DQMServices/Core/interface/ROOTFilePB.pb.h"|' ROOTFilePB.pb.cc
  grep -q '#include "DQMServices/Core/interface/ROOTFilePB.pb.h"' ROOTFilePB.pb.cc
)
