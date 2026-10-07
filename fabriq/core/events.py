"""Server-sent events: one broker, many browser tabs.

Events are small JSON objects: ``{"type": "job.updated", "job": {...}}``,
``{"type": "model.changed"}``, ``{"type": "git.changed"}``. A subscriber is
an asyncio queue; a slow one drops old events rather than blocking the rest.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator


class Broker:
    def __init__(self, max_queue: int = 256):
        self._queues: set[asyncio.Queue] = set()
        self._max_queue = max_queue
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, event: dict) -> None:
        """Publish from any thread. Safe before the loop exists (dropped)."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._publish_now, event)

    def _publish_now(self, event: dict) -> None:
        for queue in list(self._queues):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    async def subscribe(self) -> AsyncIterator[dict]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._queues.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._queues.discard(queue)

    @staticmethod
    def format(event: dict) -> str:
        """One SSE frame."""
        return f"event: {event.get('type', 'message')}\ndata: {json.dumps(event, default=str)}\n\n"
