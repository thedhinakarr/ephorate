import os
import signal
import time

import pytest

from ephorate.cli import _finalization_deadline
from ephorate.models import EphorateError


def test_blocked_output_is_bounded_and_alarm_is_restored() -> None:
    previous = signal.getsignal(signal.SIGALRM)
    read_fd, write_fd = os.pipe()
    started = time.monotonic()
    try:
        with pytest.raises(EphorateError, match="finalization_timeout"):
            with _finalization_deadline(0.05):
                while True:
                    os.write(write_fd, b"x" * 65536)
        assert time.monotonic() - started < 2
        assert signal.getsignal(signal.SIGALRM) == previous
        assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    finally:
        os.close(write_fd)
        os.close(read_fd)
