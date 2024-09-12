from __future__ import annotations

import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor


class WorkerPool(ThreadPoolExecutor):
    _instance: WorkerPool = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls, max_workers: int = None) -> WorkerPool:
        with WorkerPool._lock:
            if WorkerPool._instance is None:
                max_workers = max_workers if max_workers else multiprocessing.cpu_count()
                WorkerPool._instance = WorkerPool(max_workers)

            return WorkerPool._instance

    def __init__(self, max_workers: int) -> None:
        super().__init__(max_workers)
