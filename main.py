from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from src.config_loader import load_hotkeys
from src.process_controller import ProcessController


class LauncherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("KIRKA Launcher")
        self.root.geometry("420x230")
        self.root.resizable(False, False)

        self.base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
        self.images_dir = self.base_dir / "images"

        self.start_key, self.stop_key = load_hotkeys(self.base_dir)

        # Demo command: keep process alive in background.
        self.controller = ProcessController(
            command=[sys.executable, "-c", "import time; time.sleep(10**6)"],
            working_dir=self.base_dir,
        )

        self._build_ui()
        self._bind_hotkeys()
        self._refresh_status()

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.pack(fill="both", expand=True)

        title = ttk.Label(main_frame, text="KIRKA Launcher", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="center", pady=(0, 14))

        self.status_label = ttk.Label(main_frame, text="Status: STOPPED", font=("Segoe UI", 10))
        self.status_label.pack(anchor="center", pady=(0, 14))

        buttons = ttk.Frame(main_frame)
        buttons.pack(anchor="center", pady=(0, 12))

        self.start_btn = ttk.Button(buttons, text="Start", width=14, command=self.start)
        self.start_btn.grid(row=0, column=0, padx=8)

        self.stop_btn = ttk.Button(buttons, text="Stop", width=14, command=self.stop)
        self.stop_btn.grid(row=0, column=1, padx=8)

        info_text = (
            f"Hotkeys: '{self.start_key}' = Start, '{self.stop_key}' = Stop\n"
            f"Images folder: {self.images_dir}"
        )
        ttk.Label(main_frame, text=info_text, justify="center").pack(anchor="center")

    def _bind_hotkeys(self) -> None:
        self.root.bind(f"<{self.start_key}>", lambda _event: self.start())
        self.root.bind(f"<{self.stop_key}>", lambda _event: self.stop())

    def _refresh_status(self) -> None:
        running = self.controller.is_running
        self.status_label.configure(text=f"Status: {'RUNNING' if running else 'STOPPED'}")
        self.start_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")

    def start(self) -> None:
        try:
            self.controller.start()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Start error", str(exc))
        finally:
            self._refresh_status()

    def stop(self) -> None:
        try:
            self.controller.stop()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Stop error", str(exc))
        finally:
            self._refresh_status()


def main() -> None:
    root = tk.Tk()
    app = LauncherApp(root)

    def on_close() -> None:
        app.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
