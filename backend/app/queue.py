from collections import deque
from typing import Any, Deque, Optional


class InMemoryQueue:
    """
    Simple FIFO queue to simulate SQS/PubSub during local dev.
    Not thread-safe; suitable for single-process demo and tests.
    """

    def __init__(self, name: str):
        self.name = name
        self._queue: Deque[Any] = deque()

    def enqueue(self, item: Any) -> None:
        self._queue.append(item)

    def dequeue(self) -> Optional[Any]:
        if not self._queue:
            return None
        return self._queue.popleft()

    def __len__(self) -> int:
        return len(self._queue)

