"""Server-Sent Events helpers.

Bridges the sync progress_callback (called from worker threads) with
async SSE streaming responses.
"""

from __future__ import annotations

import asyncio

# Global map: run_id → asyncio.Queue
_queues: dict[str, asyncio.Queue[dict | None]] = {}


def create_queue(run_id: str) -> asyncio.Queue[dict | None]:
    """Create an SSE event queue for a pipeline run."""
    q: asyncio.Queue[dict | None] = asyncio.Queue()
    _queues[run_id] = q
    return q


def get_queue(run_id: str) -> asyncio.Queue[dict | None] | None:
    """Get the event queue for a run, or None if not active."""
    return _queues.get(run_id)


def remove_queue(run_id: str) -> None:
    """Clean up the queue after the SSE stream closes."""
    _queues.pop(run_id, None)


def make_progress_callback(
    run_id: str,
    loop: asyncio.AbstractEventLoop,
) -> callable:
    """Create a sync callback that pushes events into the async queue.

    The returned callback is safe to call from a worker thread — it uses
    loop.call_soon_threadsafe to enqueue events.
    """
    q = _queues[run_id]

    def callback(stage: str, status: str) -> None:
        loop.call_soon_threadsafe(q.put_nowait, {"stage": stage, "status": status})

    return callback
