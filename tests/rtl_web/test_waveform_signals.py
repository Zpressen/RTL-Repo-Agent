import signal
import subprocess
import sys

import pytest


@pytest.mark.skipif(not hasattr(signal, 'SIGPIPE'), reason='POSIX signal behavior')
def test_waveform_import_keeps_broken_connections_from_terminating_the_server():
    script = '''import os, signal
signal.signal(signal.SIGPIPE, signal.SIG_IGN)
import zerorepo.rtl_web.waveform
os.kill(os.getpid(), signal.SIGPIPE)
print("server survived broken pipe")
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert 'server survived broken pipe' in result.stdout
