import logging
import sys
from pathlib import Path
from typing import Optional, Union


class TeeStream:
    """Mirror text writes to the original stream and a log file."""

    def __init__(self, primary_stream, log_stream):
        self.primary_stream = primary_stream
        self.log_stream = log_stream
        self.encoding = getattr(primary_stream, "encoding", "utf-8")

    def write(self, data):
        if not data:
            return 0
        self.primary_stream.write(data)
        self.log_stream.write(data)
        return len(data)

    def flush(self):
        self.primary_stream.flush()
        self.log_stream.flush()

    def isatty(self):
        return bool(getattr(self.primary_stream, "isatty", lambda: False)())

    def fileno(self):
        if hasattr(self.primary_stream, "fileno"):
            return self.primary_stream.fileno()
        raise OSError("Primary stream does not support fileno()")


def redirect_standard_streams(file_path: Optional[Union[str, Path]]) -> None:
    """
    Tee stdout/stderr to the provided file while preserving console output.

    This captures plain `print(...)` output and any other direct writes to
    stdout/stderr that bypass the logging module.
    """
    if file_path is None:
        return

    fp = Path(file_path)
    fp.parent.mkdir(parents=True, exist_ok=True)

    current_stdout = sys.stdout
    current_stderr = sys.stderr
    if isinstance(current_stdout, TeeStream) and isinstance(current_stderr, TeeStream):
        current_log = getattr(current_stdout.log_stream, "name", None)
        if current_log and Path(current_log) == fp:
            return

    stdout_log = open(fp, "a", encoding="utf-8", buffering=1)
    stderr_log = open(fp, "a", encoding="utf-8", buffering=1)
    sys.stdout = TeeStream(sys.__stdout__, stdout_log)
    sys.stderr = TeeStream(sys.__stderr__, stderr_log)


def _stream_redirects_to_file(stream, file_path: Path) -> bool:
    if not isinstance(stream, TeeStream):
        return False
    current_log = getattr(stream.log_stream, "name", None)
    if not current_log:
        return False
    try:
        return Path(current_log).resolve() == file_path.resolve()
    except OSError:
        return Path(current_log) == file_path


def setup_logger(
    logger: Optional[logging.Logger] = None,
    file_path: Optional[Union[str, Path]] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Setup a logger with console output by default.
    If `file_path` is provided, also log to that file.

    - Avoids duplicate handlers when called multiple times.
    - Creates parent directory for file_path if needed.
    """
    if logger is None:
        logger = logging.getLogger("Agent")

    logger.setLevel(level)
    logger.propagate = False  # avoid double logging via root logger

    formatter = logging.Formatter(
        "[%(asctime)s][%(name)s][%(levelname)s] %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )

    # Ensure a stream handler exists
    has_stream = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
    if not has_stream:
        sh = logging.StreamHandler()
        sh.setLevel(level)
        sh.setFormatter(formatter)
        logger.addHandler(sh)

    # Optionally add a file handler
    if file_path is not None:
        fp = Path(file_path)
        fp.parent.mkdir(parents=True, exist_ok=True)

        # When stdout/stderr have already been tee'd to the same log file,
        # adding a dedicated FileHandler would duplicate every log record.
        file_already_captured_by_stream = _stream_redirects_to_file(sys.stdout, fp) or _stream_redirects_to_file(sys.stderr, fp)

        # Avoid adding the same file handler multiple times
        has_same_file = any(
            isinstance(h, logging.FileHandler) and Path(getattr(h, "baseFilename", "")) == fp
            for h in logger.handlers
        )
        if not has_same_file and not file_already_captured_by_stream:
            fh = logging.FileHandler(fp, encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(formatter)
            logger.addHandler(fh)

    return logger
