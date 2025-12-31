
#!/usr/bin/env python3
"""
Tkinter GUI for footballsim.py
--------------------------------
This GUI wraps the existing CLI simulator without requiring code changes.
It redirects prints to a transcript window and intercepts input() calls
via a thread-safe queue. The game loop runs in a background thread.

Usage:
  python ui_tk.py

Requirements:
  - Place ui_tk.py in the same folder as footballsim.py
  - Python 3.9+ with Tkinter (included by default on most platforms)

Packaging to executable: see instructions printed at runtime or README in the response.
"""

import sys
import builtins
import threading
import queue
import os
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

# Import the simulator module
import footballsim

class GuiIO:
    """File-like object to redirect stdout/stderr into the Tkinter text widget."""
    def __init__(self, append_fn):
        self._append = append_fn

    def write(self, s: str):
        if not s:
            return
        # Tkinter updates must run on main thread; schedule via after()
        self._append(s)

    def flush(self):
        # No-op; provided for compatibility
        pass

class FootballSimGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Football Simulator")
        root.geometry("920x640")

        # --- Top area: transcript ---
        self.txt = ScrolledText(root, wrap=tk.WORD, height=24)
        self.txt.configure(state=tk.DISABLED)
        self.txt.grid(row=0, column=0, columnspan=6, sticky="nsew", padx=8, pady=8)

        # Make the grid expandable
        root.grid_columnconfigure(0, weight=1)
        for c in range(1, 6):
            root.grid_columnconfigure(c, weight=0)
        root.grid_rowconfigure(0, weight=1)

        # --- Prompt label ---
        ttk.Label(root, text="Prompt:").grid(row=1, column=0, sticky="w", padx=8)
        self.prompt_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.prompt_var).grid(row=1, column=1, columnspan=5, sticky="w")

        # --- Input entry + Send ---
        self.input_var = tk.StringVar()
        self.entry = ttk.Entry(root, textvariable=self.input_var)
        self.entry.grid(row=2, column=0, columnspan=5, sticky="we", padx=8, pady=6)
        self.entry.bind('<Return>', lambda _e: self._send())
        ttk.Button(root, text="Send", command=self._send).grid(row=2, column=5, sticky="e", padx=8)

        # --- Quick action buttons for common responses ---
        quick_frame = ttk.Frame(root)
        quick_frame.grid(row=3, column=0, columnspan=6, sticky="we", padx=8, pady=6)
        self.quick_btns = {}
        for label in ["run", "pass", "deep", "punt", "fg", "stats", "score", "clock", "timeout", "quit"]:
            b = ttk.Button(quick_frame, text=label.capitalize(), command=lambda v=label: self._set_and_send(v))
            b.pack(side=tk.LEFT, padx=4)
            self.quick_btns[label] = b

        # --- Formation quick selection ---
        form_frame = ttk.Frame(root)
        form_frame.grid(row=4, column=0, columnspan=6, sticky="we", padx=8, pady=4)
        ttk.Label(form_frame, text="Defense Formation:").pack(side=tk.LEFT)
        self.form_var = tk.StringVar(value=footballsim.DEF_CHOICES[0]) if footballsim.DEF_CHOICES else tk.StringVar(value="4-3 Base")
        form_combo = ttk.Combobox(form_frame, textvariable=self.form_var, values=footballsim.DEF_CHOICES, width=18, state="readonly")
        form_combo.pack(side=tk.LEFT, padx=6)
        ttk.Button(form_frame, text="Use Formation", command=lambda: self._use_formation()).pack(side=tk.LEFT)

        # --- Thread-safe queues ---
        self.input_queue: queue.Queue[str] = queue.Queue()
        self.prompt_queue: queue.Queue[str] = queue.Queue()
        self.output_queue: queue.Queue[str] = queue.Queue()

        # Install stdout/stderr redirects
        self._stdout_prev = sys.stdout
        self._stderr_prev = sys.stderr
        sys.stdout = GuiIO(lambda s: self._append_async(s))
        sys.stderr = GuiIO(lambda s: self._append_async(s))

        # Monkey patch builtins.input for the game thread
        self._input_prev = builtins.input
        builtins.input = self._patched_input

        # Periodically drain queues to update GUI
        self._poll()

        # Start game loop in background
        self.game_thread = threading.Thread(target=self._run_game, daemon=True)
        self.game_thread.start()

        # On close, restore IO
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------- Core plumbing -------------
    def _append_async(self, s: str):
        # Collect output in a queue to append in main thread
        self.output_queue.put(s)

    def _poll(self):
        # Drain output queue
        while True:
            try:
                s = self.output_queue.get_nowait()
            except queue.Empty:
                break
            self._append_text(s)
        # Drain prompt queue
        while True:
            try:
                p = self.prompt_queue.get_nowait()
            except queue.Empty:
                break
            self.prompt_var.set(p)
        # Reschedule polling
        self.root.after(50, self._poll)

    def _append_text(self, s: str):
        self.txt.configure(state=tk.NORMAL)
        self.txt.insert(tk.END, s)
        self.txt.see(tk.END)
        self.txt.configure(state=tk.DISABLED)

    def _patched_input(self, prompt: str = "") -> str:
        # Called in game thread; push prompt to GUI and block until a response arrives
        self.prompt_queue.put(prompt)
        # Focus input box
        self.root.after(0, lambda: self.entry.focus_set())
        # Block until user sends a response
        resp = self.input_queue.get()  # type: ignore[str-bytes-safe]
        # Echo the response to transcript for context
        self._append_async(f"> {resp}\n")
        return resp

    def _send(self):
        val = self.input_var.get().strip()
        if not val:
            return
        self.input_var.set("")
        self.input_queue.put(val)

    def _set_and_send(self, value: str):
        self.input_var.set(value)
        self._send()

    def _use_formation(self):
        # Formation prompts expect a number index; we convert selection to its index+1
        try:
            choice = footballsim.DEF_CHOICES.index(self.form_var.get()) + 1
            self._set_and_send(str(choice))
        except Exception:
            # Fallback: send formation name directly
            self._set_and_send(self.form_var.get())

    def _run_game(self):
        try:
            footballsim.game()
        except SystemExit:
            pass
        except Exception as e:
            print(f"[GUI] Game thread error: {e}")

    def _on_close(self):
        # Attempt to send a quit so the game loop exits gracefully
        try:
            self.input_queue.put("quit")
        except Exception:
            pass
        # Restore IO
        try:
            builtins.input = self._input_prev
            sys.stdout = self._stdout_prev
            sys.stderr = self._stderr_prev
        except Exception:
            pass
        # Destroy window
        self.root.destroy()


def main():
    root = tk.Tk()

# --- App icon setup (cross-platform) ---
    # Prefer ICO for Windows packaging, PNG for Tk runtime icon across platforms.
    icon_png = os.path.join(os.path.dirname(__file__), "app_icon.png")
    icon_ico = os.path.join(os.path.dirname(__file__), "app_icon.ico")

    try:
        # Runtime window icon for Tk (works on Windows/macOS/Linux)
        if os.path.exists(icon_png):
            icon_img = tk.PhotoImage(file=icon_png)
            root.iconphoto(True, icon_img)
    except Exception as e:
        print(f"[GUI] iconphoto error: {e}")

    try:
        # Windows-specific icon (used if you run without PyInstaller windowed packaging)
        if os.path.exists(icon_ico) and hasattr(root, "iconbitmap"):
            root.iconbitmap(icon_ico)
    except Exception as e:
        print(f"[GUI] iconbitmap error: {e}")


    app = FootballSimGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()