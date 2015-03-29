"""retrythread.py

Implements a thread that will call an action at a set of times in the future,
and that can have more times added at any point. So:

bgthr = RetryThread(action=myaction)
bgthr.start()
# Got a background thread, but haven't scheduled any pops yet.

bgthr.addRetryTime(5.5)
# Will do a pop in 5.5 seconds.

bgthr.addRetryTime(0.0)
# Will do a pop right away (but from the background thread, not the calling
# thread).

Timing will not be very precise, and basically depends on the latency of
python's and therefore the OS's conditionlock implementation.

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
import time
import threading
import socket
import select
import logging

log = logging.getLogger(__name__)


class _FDSource(object):

    def __init__(self, selectable, action):
        if not (isinstance(selectable, int) or hasattr(selectable, "fileno")):
            raise ValueError(
                "FD object %r is not selectable (is an int or implements "
                "fileno())." % fd)

        super(_FDSource, self).__init__()
        self._fds_selectable = selectable
        self._fds_int = (
            self._fds_selectable
            if isinstance(self._fds_selectable, int) else
            self._fds_selectable.fileno())
        self._fds_action = action

    def __int__(self):
        return self._fds_int

    def newDataAvailable(self):
        self._fds_action(self._fds_selectable)


class RetryThread(threading.Thread):

    Clock = time.clock

    def __init__(self, action=None, **kwargs):
        """Callers must be careful that they do not hold references to the
        thread an pass in actions that hold references to themselves, which
        leads to a retain deadlock (each hold the other so neither are ever
        freed).

        One way to get around this is to use the weakref module to ensure
        that if the owner of this thread needs to be referenced in the action,
        the action doesn't retain the owner.
        """
        super(RetryThread, self).__init__(**kwargs)
        self._rthr_action = action
        self._rthr_cancelled = False
        self._rthr_retryTimes = []
        self._rthr_nextTimesLock = threading.Lock()

        self._rthr_fdSources = {}

        self._rthr_triggerRunFD, output = socket.socketpair()

        self.addInputFD(output, lambda selectable: selectable.recv(1))

    def __del__(self):
        log.debug("Deleting thread.")
        self.cancel()
        self.join()

    def run(self):
        """Runs until cancelled.

        Note that because this method runs until cancelled, it holds a
        reference to self, and so self cannot be garbage collected until self
        has been cancelled. Therefore along with the note about retain
        deadlocks in `__init__` callers would do well to call `cancel` in the
        owner's `__del__` method.
        """
        wait = 3600  # an hour if
        while not self._rthr_cancelled:
            log.debug("Thread not cancelled, next retry times: %r, wait: %d",
                      self._rthr_retryTimes, wait)

            rsrcs = self._rthr_fdSources.keys()
            rfds, wfds, efds = select.select(rsrcs, [], rsrcs, wait)
            self._rthr_processSelectedReadFDs(rfds)

            # Check timers.
            with self._rthr_nextTimesLock:
                numrts = len(self._rthr_retryTimes)
                if numrts == 0:
                    wait = 3600
                    continue
                next = self._rthr_retryTimes[0]

            now = self.Clock()
            if next > now:
                wait = next - now
                log.debug("Next try in %r seconds", wait)
                continue

            log.debug("Retrying as next %r <= now %r", next, now)
            action = self._rthr_action
            if action is not None:
                action()
            with self._rthr_nextTimesLock:
                del self._rthr_retryTimes[0]

            # Immediately respin since we haven't checked the next timer yet.
            wait = 0

        log.debug("Thread exiting.")

    def addInputFD(self, fd, action):
        """Add file descriptor `fd` as a source to wait for data from, with
        `action` to be called when there is data available from `fd`.
        """
        newinput = _FDSource(fd, action)
        newinputint = int(newinput)
        if newinputint in self._rthr_fdSources:
            raise ValueError(
                "Duplicate FD source %r added to thread." % newinput)

        self._rthr_fdSources[newinputint] = newinput

    def addRetryTime(self, ctime):
        """Add a time when we should retry the action. If the time is already
        in the list, then the new time is not re-added."""
        with self._rthr_nextTimesLock:
            ii = 0
            for ii, time in zip(
                    range(len(self._rthr_retryTimes)), self._rthr_retryTimes):
                if ctime < time:
                    break
                if ctime == time:
                    # This time is already present, no need to re-add it.
                    return
            else:
                ii = len(self._rthr_retryTimes)

            new_rts = list(self._rthr_retryTimes)
            new_rts.insert(ii, ctime)
            self._rthr_retryTimes = new_rts
            log.debug("Retry times: %r", self._rthr_retryTimes)

        self._rthr_triggerRunFD.send('1')

    def cancel(self):
        self._rthr_cancelled = True
        self._rthr_triggerRunFD.send('1')

    #
    # INTERNAL METHODS
    #
    def _rthr_processSelectedReadFDs(self, rfds):
        for rfd in rfds:
            fdsrc = self._rthr_fdSources[rfd]
            fdsrc.newDataAvailable()
