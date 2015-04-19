"""tsiptransport.py

Unit tests for the SIP transport.

Copyright 2015 David Park

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import sys
import os
import re
import time
import timeit
import logging
import unittest

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

import message
import transport
import siptransport

log = logging.getLogger()


class TestSIPTransport(unittest.TestCase):

    def wait_for(self, func, timeout=2):
        assert timeout > 0.05
        now = timeit.default_timer()
        until = now + timeout
        while timeit.default_timer() < until:
            if func():
                break
            time.sleep(0.01)
        else:
            self.assertTrue(0, "Timed out waiting for %r" % func)

    def testBasicSIPTransport(self):

        S = siptransport.SipTransportFSM.States
        I = siptransport.SipTransportFSM.Inputs

        t1 = siptransport.SipTransportFSM()
        t2 = siptransport.SipTransportFSM()

        t1.hit(I.listen)
        self.wait_for(lambda: t1.localAddress != (None, 0))
        log.debug("t1.localAddress: %r", t1.localAddress)
        t2.hit(I.connect, t1.localAddress)

        self.wait_for(lambda: t2.state == S.connected)
        self.wait_for(lambda: t1.state == S.connected)

        inv = message.Message.invite()
        t1.sendMessage(inv)

        self.wait_for(lambda: len(t2.messages) > 0)

        t1.hit(I.disconnect)

if __name__ == "__main__":
    unittest.main()