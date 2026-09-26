#include "tmEventSetup/tmEventSetup.hh"
#include "tmEventSetup/esTriggerMenu.hh"
#include <iostream>
#include <memory>

// Read an L1 menu from XML, as L1Trigger/L1TGlobal's ESProducer does: this goes through all
// five libraries (the XSD parser, schema validation with xerces-c, the grammar, the tables).
int main(int argc, char* argv[]) {
  if (argc != 2) {
    std::cerr << "usage: " << argv[0] << " menu.xml\n";
    return 2;
  }
  std::unique_ptr<const tmeventsetup::esTriggerMenu> menu(tmeventsetup::getTriggerMenu(argv[1]));
  std::cout << "menu " << menu->getName() << ": " << menu->getAlgorithmMap().size()
            << " algorithms, " << menu->getScaleMap().size() << " scales\n";
  return menu->getAlgorithmMap().empty() ? 1 : 0;
}
