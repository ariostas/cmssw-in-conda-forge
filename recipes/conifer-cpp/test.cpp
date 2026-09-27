// A one-split tree: x <= 0.5 gives -1, otherwise 1, scaled by norm 2
#include "conifer.h"

#include <cstdio>
#include <fstream>
#include <vector>

int main() {
  std::ofstream("bdt.json") << R"({"n_classes": 2, "n_trees": 1, "n_features": 1, "norm": 2.0,
    "init_predict": [0.0], "trees": [[{"feature": [0, -2, -2], "children_left": [1, -1, -1],
    "children_right": [2, -1, -1], "threshold": [0.5, -2.0, -2.0], "value": [0.0, -1.0, 1.0]}]]})";
  conifer::BDT<double, double> bdt("bdt.json");
  double low = bdt.decision_function({0.2}).at(0), high = bdt.decision_function({0.7}).at(0);
  std::printf("f(0.2) = %g, f(0.7) = %g\n", low, high);
  return (low == -2.0 && high == 2.0) ? 0 : 1;
}
