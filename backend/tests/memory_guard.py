"""Memory check before the tests that load the real embedding models.

Those tests keep the PyTorch and the ONNX model in memory at the same time (peak of about
1.5 GB measured). Started while other heavy programs were running, they exhausted the RAM of
the development PC twice: Linux froze on swap instead of stopping a process.
"""

from pathlib import Path

REQUIRED_MEMORY_MB = 2048

MEMORY_WARNING = (
    "ATTENZIONE: i test che verranno eseguiti richiedono parecchia memoria. "
    "Assicurarsi di liberare almeno 2 GB di RAM prima di lanciare i test, per non mandare in crash il sistema."
)


def available_memory_mb(meminfo: Path = Path("/proc/meminfo")) -> int | None:
    """Reads the memory the Linux kernel considers available for new programs.

    MemAvailable includes the cache the kernel can free, so it is the right measure,
    unlike MemFree, which is low on any system that has been running for a while.

    Args:
        meminfo: File to read; tests pass a fake one.

    Returns:
        The available memory in MB, or None where it cannot be read (e.g. on Windows).
    """
    try:
        lines = meminfo.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        # Format: "MemAvailable:    8573112 kB"
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return None


def low_memory_message(available_mb: int | None, required_mb: int = REQUIRED_MEMORY_MB) -> str | None:
    """Explains why the tests must not start, if the memory is not enough.

    Args:
        available_mb: Available memory, or None if it could not be measured.
        required_mb: Minimum memory needed by the real-model tests.

    Returns:
        The message to show when stopping, or None if the tests can start. An unknown
        amount of memory does not stop the tests: the warning has already been shown.
    """
    if available_mb is None or available_mb >= required_mb:
        return None
    return (
        f"Test interrotti prima di caricare i modelli: sono disponibili solo {available_mb} MB di RAM, "
        f"ne servono almeno {required_mb}. Libera memoria chiudendo i programmi che ne usano di più, poi rilancia."
    )
