import io
import sys

from zerorepo.utils.logs import TeeStream


def test_tee_stream_writes_to_console_and_log():
    console = io.StringIO()
    log_file = io.StringIO()
    tee = TeeStream(console, log_file)

    written = tee.write("hello log\n")
    tee.flush()

    assert written == len("hello log\n")
    assert console.getvalue() == "hello log\n"
    assert log_file.getvalue() == "hello log\n"


def test_tee_stream_is_tty_follows_primary_stream():
    primary = io.StringIO()
    log_file = io.StringIO()
    tee = TeeStream(primary, log_file)

    assert tee.isatty() is False
    try:
        tee.fileno()
    except OSError:
        pass
    else:
        raise AssertionError("Expected fileno() to fail for StringIO-backed TeeStream")
