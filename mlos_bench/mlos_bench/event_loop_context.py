#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""EventLoopContext class definition."""

import asyncio
import logging
import sys
from asyncio import AbstractEventLoop
from collections.abc import Coroutine
from concurrent.futures import Future
from threading import Lock as ThreadLock
from threading import Thread
from typing import Any, TypeAlias, TypeVar

CoroReturnType = TypeVar("CoroReturnType")  # pylint: disable=invalid-name
"""Type variable for the return type of an :external:py:mod:`asyncio` coroutine."""

FutureReturnType: TypeAlias = Future[CoroReturnType]
"""Type variable for the return type of a :py:class:`~concurrent.futures.Future`."""

_LOG = logging.getLogger(__name__)


class EventLoopContext:
    """
    EventLoopContext encapsulates a background thread for :external:py:mod:`asyncio`
    event loop processing as an aid for context managers.

    There is generally only expected to be one of these, either as a base class instance
    if it's specific to that functionality or for the full mlos_bench process to support
    parallel trial runners, for instance.

    It's :py:meth:`.enter` and :py:meth:`.exit` routines are expected to be called
    from the caller's context manager routines (e.g., __enter__ and __exit__).
    """

    def __init__(self) -> None:
        self._event_loop: AbstractEventLoop | None = None
        self._event_loop_thread: Thread | None = None
        self._event_loop_thread_lock = ThreadLock()
        self._event_loop_thread_refcnt: int = 0

    def _run_event_loop(self) -> None:
        """Runs the asyncio event loop in a background thread."""
        assert self._event_loop is not None
        asyncio.set_event_loop(self._event_loop)
        self._event_loop.run_forever()

    def enter(self) -> None:
        """Manages starting the background thread for event loop processing."""
        # Start the background thread if it's not already running.
        with self._event_loop_thread_lock:
            if not self._event_loop_thread:
                assert self._event_loop_thread_refcnt == 0
                if self._event_loop is None:
                    if sys.platform == "win32":
                        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                    self._event_loop = asyncio.new_event_loop()
                assert not self._event_loop.is_running()
                self._event_loop_thread = Thread(target=self._run_event_loop, daemon=True)
                self._event_loop_thread.start()
            self._event_loop_thread_refcnt += 1

    def exit(self) -> None:
        """Manages cleaning up the background thread for event loop processing."""
        with self._event_loop_thread_lock:
            self._event_loop_thread_refcnt -= 1
            assert self._event_loop_thread_refcnt >= 0
            if self._event_loop_thread_refcnt == 0:
                assert self._event_loop is not None
                self._event_loop.call_soon_threadsafe(self._event_loop.stop)
                _LOG.info("Waiting for event loop thread to stop...")
                assert self._event_loop_thread is not None
                self._event_loop_thread.join(timeout=3)
                if self._event_loop_thread.is_alive():
                    raise RuntimeError("Failed to stop event loop thread.")
                self._event_loop_thread = None

    def run_coroutine(self, coro: Coroutine[Any, Any, CoroReturnType]) -> FutureReturnType:
        """
        Runs the given coroutine in the background event loop thread and returns a
        Future that can be used to wait for the result.

        Parameters
        ----------
        coro : Coroutine[Any, Any, CoroReturnType]
            The coroutine to run.

        Returns
        -------
        concurrent.futures.Future[CoroReturnType]
            A future that will be completed when the coroutine completes.
        """
        assert self._event_loop_thread_refcnt > 0
        assert self._event_loop is not None
        return asyncio.run_coroutine_threadsafe(coro, self._event_loop)
