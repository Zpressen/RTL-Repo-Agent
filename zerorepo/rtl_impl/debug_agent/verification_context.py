"""Optional trusted verification routing. Legacy CLI has no Web dependency."""
from contextlib import contextmanager
from contextvars import ContextVar
import os

_syntax=ContextVar('rtl_scoped_syntax_checker',default=None)


def active_syntax_checker():
    checker=_syntax.get()
    if checker is None and os.environ.get('ZEROREPO_WORKBENCH_JOB')=='1':
        raise RuntimeError('Custom HDL requires a verification context; host fallback is forbidden')
    return checker


@contextmanager
def verification_context(checker):
    token=_syntax.set(checker)
    try:yield
    finally:_syntax.reset(token)
