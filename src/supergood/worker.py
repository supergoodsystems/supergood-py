import os
import threading
from collections.abc import Callable
from queue import Empty, Full, Queue
from time import sleep
from typing import Optional


# A version of the threading.Timer class with 2 differences:
#  - instead of running the function once after <interval> seconds, it loops and runs again <interval> seconds later
#  - also, runs the provided function immediately on start (for initital config fetch)
class Repeater(threading.Timer):
    def run(self):
        if not self.finished.is_set():
            self.function(*self.args, **self.kwargs)
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


class Worker:
    def __init__(self, repeater):
        # type: (Callable[[dict],None], Optional[int]) -> None
        # print(f"[{os.getpid()}] worker init")
        self._queue = Queue(42)
        self._lock = threading.Lock()
        self._thread = None
        self._pid = None
        self._fn = repeater

    @property
    def is_alive(self):
        # type: () -> bool
        if self._pid != os.getpid():
            # This case occurs when an initialized client has been forked
            #  threads do not get persisted on fork, so they must be re-started
            return False
        if not self._thread:
            return True
        return self._thread.is_alive()

    def _ensure_running(self):
        # type: () -> None
        if not self.is_alive:
            self.start()

    def start(self):
        # type: () -> None
        with self._lock:
            if not self.is_alive:
                self._thread = threading.Thread(
                    target=self._run, name="supergood-repeater"
                )
                self._thread.daemon = True
                try:
                    self._thread.start()
                    self._pid = os.getpid()
                except RuntimeError:
                    # thread init failed.
                    # May be out of available thread ids, or shutting down
                    self._thread = None

    def flush(self):
        # type: () -> None
        with self._lock:
            if self._thread:
                try:
                    self._queue.put_nowait({})
                except Full:
                    # full, drop events
                    pass

    def kill(self):
        # type: () -> None
        with self._lock:
            if self._thread:
                try:
                    self._queue.put_nowait(None)
                except Full:
                    # full, drop events
                    pass
                self._thread = None
                self._pid = None

    def append(self, entry):
        # type: (dict) -> None
        self._ensure_running()
        with self._lock:
            try:
                self._queue.put(entry)
                return True
            except Full as e:
                # full, drop events
                return False

    def _run(self):
        # type: () -> None
        while True:
            entries = {}
            # get() blocks here. it should receive a None object to terminate gracefully
            entry = self._queue.get()
            if entry is None:
                # terminate
                return
            entries.update(entry)
            # once we've gotten _a_ thing, check to see if we can bundle a few together. Up to 10
            terminate = False
            for _ in range(10):
                try:
                    entry = self._queue.get_nowait()
                    if entry is None:
                        # terminate
                        terminate = True
                        break
                    entries.update(entry)
                except Empty:
                    # nothing else to do immediately, flush what you got
                    break

            if len(entries) != 0:
                # TODO: invoke this with a timeout?
                self._fn(entries)
            elif terminate:
                return
            else:
                sleep(0)
