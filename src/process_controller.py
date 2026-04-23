from __future__ import annotations

import subprocess
from pathlib import Path


class ProcessController:
    def __init__(self, command: list[str], working_dir: Path) -> None:
        self.command = command
        self.working_dir = working_dir
        self._process: subprocess.Popen[str] | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        if self.is_running:
            return

        self._process = subprocess.Popen(
            self.command,
            cwd=str(self.working_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def stop(self) -> None:
        if not self.is_running:
            return

        assert self._process is not None
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5)
        finally:
            self._process = None
