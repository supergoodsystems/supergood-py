import time

from supergood.repeating_thread import RepeatingThread


class TestRepeatingThread:
    def test_repeating_thread(self):
        class A:
            def inc(self):
                self.i = self.i + 1

            def __init__(self):
                self.i = 0
                self.thread = RepeatingThread(self.inc, 1)

            def start(self):
                self.thread.start()

            def cancel(self):
                self.thread.cancel()

        a = A()
        assert a.thread._thread == None
        a.start()
        for i in range(1, 3):
            time.sleep(1.1)
            assert a.i == i
        a.cancel()
        assert a.thread._thread.finished.is_set()
