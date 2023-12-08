from threading import Timer


class RepeatingThread(object):
    def __init__(self, func, interval, *args, **kwargs):
        self._thread = None
        self.interval = interval
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._running = False

    def _run_one(self):
        self._running = False
        self.start()
        self.func(*self.args, **self.kwargs)

    def start(self):
        if not self._running:
            self._thread = Timer(self.interval, self._run_one)
            self._thread.daemon = True
            self._thread.start()
            self._running = True

    def cancel(self):
        if self._thread:
            self._thread.cancel()
        self._running = False
