import sys
from pathlib import Path
from typing import IO


class InstanceLock:
    """Prevents a second copy of the app from running on the same data folder.

    Two copies would open two windows on two servers writing the same SQLite file. The
    lock is taken by the operating system on an open file: if the app crashes, the
    system releases it, so there is never a stale lock to remove by hand.
    """

    def __init__(self, lock_file: Path) -> None:
        """Prepares the lock without taking it.

        Args:
            lock_file: File used as lock, inside the user data folder.
        """
        self._lock_file = lock_file
        self._handle: IO[str] | None = None

    def acquire(self) -> bool:
        """Tries to take the lock without waiting.

        Returns:
            True if this process now holds the lock, False if another process holds it.
        """
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self._lock_file, "a+", encoding="utf-8")  # noqa: SIM115 - kept open while the app runs
        try:
            if sys.platform == "win32":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        """Releases the lock, if held."""
        if self._handle is None:
            return
        if sys.platform == "win32":
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None
