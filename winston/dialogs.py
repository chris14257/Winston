"""winston.dialogs  –  text-buffer + hierarchical dialog tree."""
from __future__ import annotations
from queue import SimpleQueue
from typing import Dict, Iterator, List, Optional, Tuple
# ──────────────────────────────────────────────────────────────────────────────
# Selection helper
# ──────────────────────────────────────────────────────────────────────────────
class Selection:
    """Represents an anchor+extent selection inside a Dialog."""
    def __init__(self) -> None:
        self.reset()
    # public --------------------------------------------------------------
    def reset(self) -> None:
        self.start_line = self.start_offset = None
        self.end_line = self.end_offset = None
    def set_anchor(self, line: int, offset: int) -> None:
        self.start_line = self.end_line = line
        self.start_offset = self.end_offset = offset
    def update_end(self, line: int, offset: int) -> None:
        self.end_line, self.end_offset = line, offset
    def is_active(self) -> bool:
        return (
            self.start_line is not None
            and (
                self.start_line != self.end_line
                or self.start_offset != self.end_offset
            )
        )
    def ordered(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """Return ((first_line, first_off), (last_line, last_off))."""
        if (self.start_line, self.start_offset) <= (self.end_line, self.end_offset):
            return (self.start_line, self.start_offset), (
                self.end_line,
                self.end_offset,
            )
        return (
            (self.end_line, self.end_offset),
            (self.start_line, self.start_offset),
        )
# ──────────────────────────────────────────────────────────────────────────────
# Dialog tree + buffer
# ──────────────────────────────────────────────────────────────────────────────
class Dialog:
    """Composite node *and* line-oriented text buffer."""
    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def __init__(self, name: Optional[str] = None, value: Optional[str] = None):
        # Store name in a separate slot to avoid clashing with Thread.name
        self._dlg_name = name
        self.value = value  # populated on leaf nodes (lines)
        self.parent: Optional["Dialog"] = None
        self.key_q: Optional[SimpleQueue[str]] = None
        self._named: Dict[str, Dialog] = {}
        self._unnamed: List[Dialog] = []
        self.cursor_line: Optional[int] = None
        self.cursor_offset: int = 0
        self.selection = Selection()
    # ------------------------------------------------------------------ #
    # Name property (safe with Thread multiple inheritance)
    # ------------------------------------------------------------------ #
    @property
    def name(self) -> Optional[str]:
        return self._dlg_name
    # ------------------------------------------------------------------ #
    # Child-dialog helpers
    # ------------------------------------------------------------------ #
    def add(self, dialog: "Dialog") -> None:
        if dialog.name is None:
            raise ValueError("Named child must have a name.")
        if dialog.name in self._named:
            raise ValueError(f"Child {dialog.name!r} already exists.")
        dialog.parent = self
        dialog.key_q = self.key_q
        self._named[dialog.name] = dialog
        setattr(self, dialog.name, dialog)
    # Attribute access
    def __getattr__(self, item: str) -> "Dialog":
        try:
            return self._named[item]
        except KeyError as exc:
            raise AttributeError(f"No named child {item!r}") from exc
    # ------------------------------------------------------------------ #
    # Text-line helpers
    # ------------------------------------------------------------------ #
    def add_line(self, value: str = "") -> "Dialog":
        line = Dialog(value=value)
        line.parent = self
        line.key_q = self.key_q
        self._unnamed.append(line)
        if self.cursor_line is None:
            self.cursor_line = 0
        return line
    def lines(self) -> List[str]:
        return [(dlg.value or "") for dlg in self._unnamed]
    # Cursor-movement methods -------------------------------------------
    def move_left(self, is_shifted: bool = False) -> None:
        if self.cursor_line is None:
            return
        prev_line, prev_off = self.cursor_line, self.cursor_offset
        if self.cursor_offset > 0:
            self.cursor_offset -= 1
        elif self.cursor_line > 0:
            self.cursor_line -= 1
            self.cursor_offset = len(self._unnamed[self.cursor_line].value or "")
        self._update_selection(is_shifted, prev_line, prev_off)
    def move_right(self, is_shifted: bool = False) -> None:
        if self.cursor_line is None:
            return
        prev_line, prev_off = self.cursor_line, self.cursor_offset
        line_text = self._unnamed[self.cursor_line].value or ""
        if self.cursor_offset < len(line_text):
            self.cursor_offset += 1
        elif self.cursor_line + 1 < len(self._unnamed):
            self.cursor_line += 1
            self.cursor_offset = 0
        self._update_selection(is_shifted, prev_line, prev_off)
    def move_up(self, is_shifted: bool = False) -> None:
        if self.cursor_line is None or self.cursor_line == 0:
            return
        prev_line, prev_off = self.cursor_line, self.cursor_offset
        self.cursor_line -= 1
        line_len = len(self._unnamed[self.cursor_line].value or "")
        self.cursor_offset = min(self.cursor_offset, line_len)
        self._update_selection(is_shifted, prev_line, prev_off)
    def move_down(self, is_shifted: bool = False) -> None:
        if self.cursor_line is None or self.cursor_line + 1 >= len(self._unnamed):
            return
        prev_line, prev_off = self.cursor_line, self.cursor_offset
        self.cursor_line += 1
        line_len = len(self._unnamed[self.cursor_line].value or "")
        self.cursor_offset = min(self.cursor_offset, line_len)
        self._update_selection(is_shifted, prev_line, prev_off)
    def move_home(self, is_shifted: bool = False) -> None:
        if self.cursor_line is None:
            return
        prev_line, prev_off = self.cursor_line, self.cursor_offset
        self.cursor_offset = 0
        self._update_selection(is_shifted, prev_line, prev_off)
    def move_end(self, is_shifted: bool = False) -> None:
        if self.cursor_line is None:
            return
        prev_line, prev_off = self.cursor_line, self.cursor_offset
        self.cursor_offset = len(self._unnamed[self.cursor_line].value or "")
        self._update_selection(is_shifted, prev_line, prev_off)
    # Editing methods ----------------------------------------------------
    def insert_char(self, ch: str) -> None:
        if self.cursor_line is None:
            self.add_line("")
            self.cursor_line = 0
        if self.selection.is_active():
            self._delete_selection()
        line = self._unnamed[self.cursor_line]
        text = line.value or ""
        line.value = text[: self.cursor_offset] + ch + text[self.cursor_offset :]
        self.cursor_offset += 1
    def delete_left(self) -> None:
        if self.selection.is_active():
            self._delete_selection()
            return
        if self.cursor_line is None or (self.cursor_line == 0 and self.cursor_offset == 0):
            return
        line = self._unnamed[self.cursor_line]
        if self.cursor_offset > 0:
            text = line.value or ""
            line.value = text[: self.cursor_offset - 1] + text[self.cursor_offset :]
            self.cursor_offset -= 1
        else:
            # merge with previous line
            prev = self._unnamed[self.cursor_line - 1]
            prev_len = len(prev.value or "")
            prev.value = (prev.value or "") + (line.value or "")
            del self._unnamed[self.cursor_line]
            self.cursor_line -= 1
            self.cursor_offset = prev_len
    def delete_right(self) -> None:
        if self.selection.is_active():
            self._delete_selection()
            return
        if self.cursor_line is None:
            return
        line = self._unnamed[self.cursor_line]
        text = line.value or ""
        if self.cursor_offset < len(text):
            line.value = text[: self.cursor_offset] + text[self.cursor_offset + 1 :]
        elif self.cursor_line + 1 < len(self._unnamed):
            # merge with next line
            next_line = self._unnamed[self.cursor_line + 1]
            line.value = text + (next_line.value or "")
            del self._unnamed[self.cursor_line + 1]
    def split_line(self) -> None:
        if self.cursor_line is None:
            self.add_line("")
            self.cursor_line = 0
        line = self._unnamed[self.cursor_line]
        text = line.value or ""
        before, after = text[: self.cursor_offset], text[self.cursor_offset :]
        line.value = before
        new_line = Dialog(value=after)
        new_line.parent = self
        self._unnamed.insert(self.cursor_line + 1, new_line)
        self.cursor_line += 1
        self.cursor_offset = 0
    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _update_selection(
        self, is_shifted: bool, prev_line: int, prev_offset: int
    ) -> None:
        if is_shifted:
            if not self.selection.is_active():
                self.selection.set_anchor(prev_line, prev_offset)
            self.selection.update_end(self.cursor_line, self.cursor_offset)
        else:
            self.selection.reset()
    def _delete_selection(self) -> None:
        (s_line, s_off), (e_line, e_off) = self.selection.ordered()
        if s_line == e_line:
            line = self._unnamed[s_line]
            text = line.value or ""
            line.value = text[:s_off] + text[e_off:]
        else:
            # first line keep left side
            first = self._unnamed[s_line]
            first.value = (first.value or "")[:s_off]
            # last line keep right side
            last = self._unnamed[e_line]
            last_right = (last.value or "")[e_off:]
            # remove middle lines
            del self._unnamed[s_line + 1 : e_line + 1]
            # append right side
            first.value = (first.value or "") + last_right
        self.cursor_line, self.cursor_offset = s_line, s_off
        self.selection.reset()
    # ------------------------------------------------------------------ #
    # Debug helper
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:  # noqa: D401
        return (
            f"Dialog(name={self.name!r}, lines={len(self._unnamed)}, "
            f"cursor=({self.cursor_line},{self.cursor_offset}))"
        )