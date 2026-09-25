#include "classlib/iobase/InetServerSocket.h"
#include "classlib/iobase/IOSelector.h"
#include "classlib/utils/Error.h"
#include <cstdio>

int main() {
  // an ephemeral port on the loopback interface, as DQMNet's server does
  lat::InetServerSocket server(lat::InetAddress("127.0.0.1", static_cast<unsigned short>(0)), 1);
  lat::IOSelector selector;
  selector.attach(&server, lat::IOAccept);
  std::printf("listening on port %d\n", server.sockname().port());
  server.close();
  return 0;
}
