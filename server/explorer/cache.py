from __future__ import annotations

import os.path
import threading
import time
from abc import abstractmethod
from typing import Optional, Union

from saas.core.helpers import get_timestamp_now, write_json_to_file
from saas.core.logging import Logging

logger = Logging.get('explorer.cache')


class CachedObject:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_used = get_timestamp_now()

    def has_expired(self, expiry: int) -> bool:
        """
        Checks if the object has expired.
        :param expiry: the time period (in seconds) after which an object is considered expired.
        :return:
        """
        with self._lock:
            t_now = get_timestamp_now()
            t_expire = self._last_used + expiry * 1000
            return t_now >= t_expire

    def touch(self) -> None:
        self._last_used = get_timestamp_now()

    @abstractmethod
    def persist(self) -> None:
        pass

    @abstractmethod
    def path(self) -> str:
        pass

    @abstractmethod
    def release(self) -> None:
        pass


class CachedJSONObject(CachedObject):
    def __init__(self, content: Union[dict, list], path: str) -> None:
        super().__init__()
        self._content = content
        self._path = path

        # separate filename from folder
        d_path = os.path.dirname(path)
        if not os.path.isdir(d_path):
            logger.warning(f"Directory at {d_path} for cached JSON object does not exist -> creating.")
            os.makedirs(d_path, exist_ok=True)

    def content(self) -> Union[dict, list]:
        self.touch()
        return self._content

    def persist(self) -> str:
        if self.content() is not None:
            write_json_to_file(self._content, self._path)
            self.touch()
        return self._path

    def path(self) -> str:
        return self._path

    def release(self) -> None:
        if os.path.isfile(self._path):
            os.remove(self._path)


class Cache:
    _instance: Cache = None
    _lock = threading.Lock()

    @classmethod
    def create(cls, path: str, interval: int = 10*60, expiry: int = 60*60) -> Cache:
        with Cache._lock:
            if Cache._instance is None:
                Cache._instance = Cache(path, interval, expiry)
            return Cache._instance

    @classmethod
    def instance(cls) -> Cache:
        return Cache._instance

    def __init__(self, path: str, interval: int = 10*60, expiry: int = 60*60) -> None:
        self._lock = threading.Lock()
        self._path = path
        self._objects = {}
        self._worker = threading.Thread(target=self._prune, kwargs={
            'interval': interval,
            'expiry': expiry
        }, daemon=True)
        self._worker.start()

    def json(self, cache_obj_id: str, content: dict = None) -> Optional[CachedJSONObject]:
        with self._lock:
            # use existing content?
            if content is not None:
                path = os.path.join(self._path, cache_obj_id)
                self._objects[cache_obj_id] = CachedJSONObject(content, path)

            return self._objects.get(cache_obj_id)

    def remove(self, cache_obj_id: str) -> Optional[CachedObject]:
        with self._lock:
            if cache_obj_id in self._objects:
                obj = self._objects.pop(cache_obj_id)
                obj.release()
                return obj

        return None

    def _prune(self, interval: int, expiry: int) -> None:
        """
        Prunes the cache by checking each object in a regular interval. The cache may contain many objects and
        pruning must not block the Cache. Therefore it is implemented in such a way as to safely carry out pruning
        without unreasonably blocking the cache.
        :param interval: the time period  (in seconds) to wait before attempting to prune
        :param expiry: the time period  (in seconds) after which an object expires
        :return:
        """
        while True:
            # get a list of the keys first...
            with self._lock:
                keys = [*self._objects.keys()]

            # ...then check the object for each key. keys may no longer be available because we allow other
            # threads to potentially modify self._objects.
            for key in keys:
                with self._lock:
                    obj: CachedObject = self._objects[key] if key in self._objects else None
                    if obj.has_expired(expiry):
                        obj.release()
                        self._objects.pop(key)

            # sleep for a while
            time.sleep(interval)


