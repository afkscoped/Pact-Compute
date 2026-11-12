"""Bounded retries for retriable database errors.

Every wrapped endpoint performs its writes in one transaction that rolls back completely on
error, and its accepted-operation identity (idempotency key, quote id, lease fence) is stable,
so running the handler again in a fresh transaction is safe.
"""
import functools
import logging
import random
import time

from sqlalchemy.exc import DBAPIError

LOGGER = logging.getLogger(__name__)
# serialization failure, deadlock, lock not available, admin shutdown, connection failures
RETRIABLE_SQLSTATES = {'40001', '40P01', '55P03', '57P01', '08000', '08001', '08003', '08006'}
SLEEP = time.sleep  # replaceable in tests


def retriable(error: BaseException) -> bool:
    if not isinstance(error, DBAPIError):
        return False
    if error.connection_invalidated:
        return True
    orig = error.orig
    message = str(orig).lower()
    if 'database is locked' in message or 'database table is locked' in message:
        return True
    code = None
    if orig is not None and orig.args and isinstance(orig.args[0], dict):
        code = orig.args[0].get('C')  # pg8000 error payload
    code = code or getattr(orig, 'sqlstate', None) or getattr(orig, 'pgcode', None)
    return code in RETRIABLE_SQLSTATES


def retry_db(function=None, *, attempts: int = 3):
    def decorate(handler):
        @functools.wraps(handler)
        def run(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return handler(*args, **kwargs)
                except DBAPIError as error:
                    if attempt == attempts or not retriable(error):
                        raise
                    LOGGER.warning('Retrying %s after retriable database error (attempt %d of %d)', handler.__name__, attempt, attempts)
                    SLEEP(min(0.05 * 2 ** attempt, 0.4) * (0.5 + random.random()))
        return run
    return decorate(function) if function else decorate
