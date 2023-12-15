from threading import Timer


class RepeatingThread(object):
    """
    A function to help run a thread every `interval` seconds
    `skip_first_interval` will not wait for the first interval before running
    """

    def __init__(self, func, interval, skip_first_interval=False, *args, **kwargs):
        self._thread = None
        self.interval = interval
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._running = False
        self.skip_first_interval = skip_first_interval

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
