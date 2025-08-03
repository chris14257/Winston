"""winston.applets.editor  –  minimal keystroke-driven text editor."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Optional
from winston.anchor import AppletDialog, ModifiedKey, key
class EditorApplet(AppletDialog):
    """A line-oriented editor applet suitable for screen-reader output."""
    DEFAULT_NAME = "untitled.txt"
    def __init__(self, anchor, name: str = "editor") -> None:
        super().__init__(anchor, name)
        # Ensure buffer has at least one line
        if not self._unnamed:
            self.add_line("")
        # Remember last-used filename (None until first save)
        self._filename: Optional[Path] = None
    # ──────────────────────────────────────────────────────────────────────
    # Command bindings
    # ──────────────────────────────────────────────────────────────────────
    @key("control+s")
    def command_save(self, mk: ModifiedKey) -> None:
        """Save buffer.  Shift ⇒ save-as."""
        if mk.shift or self._filename is None:
            # TODO: replace with real file-save dialog
            self._filename = Path(self.DEFAULT_NAME)
        with self._filename.open("w", encoding="utf-8") as fp:
            fp.write("\n".join(self.lines()))
        # Placeholder TTS hook (will wire to speech later)
        print(f"[Editor] Saved {self._filename}")
    # Arrow keys
    @key("left")
    def command_left(self, mk: ModifiedKey) -> None:
        self.move_left(is_shifted=mk.shift)
    @key("right")
    def command_right(self, mk: ModifiedKey) -> None:
        self.move_right(is_shifted=mk.shift)
    @key("up")
    def command_up(self, mk: ModifiedKey) -> None:
        self.move_up(is_shifted=mk.shift)
    @key("down")
    def command_down(self, mk: ModifiedKey) -> None:
        self.move_down(is_shifted=mk.shift)
    # Home / End
    @key("home")
    def command_home(self, mk: ModifiedKey) -> None:
        self.move_home(is_shifted=mk.shift)
    @key("end")
    def command_end(self, mk: ModifiedKey) -> None:
        self.move_end(is_shifted=mk.shift)
    # Editing
    @key("enter")
    def command_enter(self, mk: ModifiedKey) -> None:
        self.split_line()
    @key("backspace")
    def command_backspace(self, mk: ModifiedKey) -> None:
        self.delete_left()
    @key("delete")
    def command_delete(self, mk: ModifiedKey) -> None:
        self.delete_right()
    # ──────────────────────────────────────────────────────────────────────
    # Fallback for characters that have no explicit binding
    # ──────────────────────────────────────────────────────────────────────
    def unbound_key(self, mk: ModifiedKey) -> None:
        if len(mk.key) == 1 and mk.key.isprintable():
            ch = mk.key.upper() if mk.shift else mk.key
            self.insert_char(ch)
    # ──────────────────────────────────────────────────────────────────────
    # Optional focus hooks
    # ──────────────────────────────────────────────────────────────────────
    def on_activate(self) -> None:
        # Announce activation; placeholder until TTS layer is wired in.
        print("[Editor] Activated")
        time.sleep(0.01)  # give any speech buffer time to flush
    def on_deactivate(self) -> None:
        print("[Editor] Deactivated")