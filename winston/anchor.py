"""winston.anchor
Top-level application orchestrator plus Applet base-class hierarchy.
Matches the multi-inheritance design we discussed: AppletDialog
inherits from both Dialog and threading.Thread.
"""
from __future__ import annotations
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Type
from winston.dialogs import Dialog  # your earlier buffer tree
__all__ = ["ModifiedKey", "key", "AppletDialog", "Anchor"]
# ──────────────────────────────────────────────────────────────────────────────
# Key abstraction
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class ModifiedKey:
    key: str
    ctrl: bool = False
    alt: bool = False
    shift: bool = False
    meta: bool = False
    def __str__(self) -> str:  # noqa: D401
        mods: List[str] = []
        if self.ctrl:
            mods.append("Ctrl")
        if self.alt:
            mods.append("Alt")
        if self.shift:
            mods.append("Shift")
        if self.meta:
            mods.append("Meta")
        mods.append(self.key.upper() if len(self.key) == 1 else self.key)
        return "+".join(mods)
def _canon(mk: "ModifiedKey") -> str:
    parts: List[str] = []
    if mk.ctrl:
        parts.append("control")
    if mk.alt:
        parts.append("alt")
    if mk.shift:
        parts.append("shift")
    if mk.meta:
        parts.append("meta")
    parts.append(mk.key.lower())
    return "+".join(parts)
# ──────────────────────────────────────────────────────────────────────────────
# Decorator to bind keys to command_ methods
# ──────────────────────────────────────────────────────────────────────────────
def key(binding: str):
    binding_norm = binding.lower()
    def decorator(func):
        setattr(func, "_key_binding", binding_norm)
        return func
    return decorator
# ──────────────────────────────────────────────────────────────────────────────
# Applet base-class  (Dialog + Thread)
# ──────────────────────────────────────────────────────────────────────────────
class AppletDialog(Dialog, threading.Thread):
    KEY_POLL_INTERVAL = 0.05  # seconds
    def __init__(self, anchor: "Anchor", name: str):
        Dialog.__init__(self, name=name)
        threading.Thread.__init__(self, daemon=True, name=name)
        self.anchor = anchor
        self.key_q: "queue.Queue[ModifiedKey]" = queue.Queue()
        self._running = threading.Event()
        self._bindings: Dict[str, Callable[[ModifiedKey], None]] = {}
        self._discover_bindings()
    # binding discovery
    def _discover_bindings(self) -> None:
        for attr_name in dir(self):
            if not attr_name.startswith("command_"):
                continue
            func = getattr(self, attr_name)
            binding = getattr(func, "_key_binding", None)
            if binding:
                self._bindings[binding] = func  # type: ignore[arg-type]
    # thread main loop
    def run(self) -> None:  # noqa: D401
        self._running.set()
        self.on_activate()
        try:
            while self._running.is_set():
                try:
                    key_obj = self.key_q.get(timeout=self.KEY_POLL_INTERVAL)
                except queue.Empty:
                    continue
                self._dispatch(key_obj)
        finally:
            self.on_deactivate()
    def stop(self) -> None:
        self._running.clear()
    # key dispatcher
    def _dispatch(self, mk: ModifiedKey) -> None:
        canon = _canon(mk)
        func = self._bindings.get(canon)
        if not func and mk.shift:
            canon_noshift = canon.replace("shift+", "")
            func = self._bindings.get(canon_noshift)
        if func:
            func(mk)  # type: ignore[misc]
        else:
            self.unbound_key(mk)
    # overridables --------------------------------------------------------
    def unbound_key(self, mk: ModifiedKey) -> None:  # noqa: D401
        pass
    def on_activate(self) -> None:  # noqa: D401
        pass
    def on_deactivate(self) -> None:  # noqa: D401
        pass
# ──────────────────────────────────────────────────────────────────────────────
# Anchor  – message pump + applet router
# ──────────────────────────────────────────────────────────────────────────────
class Anchor:
    def __init__(self) -> None:
        self.applets: Dict[str, AppletDialog] = {}
        self._applet_classes: Dict[str, Type[AppletDialog]] = {}
        self._active_name: Optional[str] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._raw_key_q: "queue.Queue[ModifiedKey]" = queue.Queue()
        self._running = threading.Event()
    # registration
    def register_applet(self, name: str, klass: Type[AppletDialog]) -> None:
        if name in self._applet_classes:
            raise ValueError(f"Applet '{name}' already registered")
        self._applet_classes[name] = klass
    def activate(self, name: str) -> None:
        if name not in self._applet_classes:
            raise KeyError(name)
        if name not in self.applets:
            applet = self._applet_classes[name](anchor=self, name=name)
            self.applets[name] = applet
            applet.start()
        if self._active_name and self._active_name in self.applets:
            self.applets[self._active_name].on_deactivate()
        self._active_name = name
        self.applets[name].on_activate()
    # main pump
    def run(self) -> None:  # noqa: D401
        self._running.set()
        self._start_listener()
        try:
            while self._running.is_set():
                try:
                    mk = self._raw_key_q.get(timeout=0.05)
                except queue.Empty:
                    continue
                if self._active_name and self._active_name in self.applets:
                    self.applets[self._active_name].key_q.put(mk)
        finally:
            self.stop()
    def stop(self) -> None:
        self._running.clear()
        if self._listener_thread:
            self._listener_thread.join(timeout=1)
        for app in self.applets.values():
            app.stop()
            app.join(timeout=1)
    # key-listener
    def _start_listener(self) -> None:
        if self._listener_thread:
            return
        def _listen() -> None:
            try:
                from pynput import keyboard  # type: ignore
            except ImportError:
                while self._running.is_set():
                    time.sleep(0.1)
                return
            def on_press(key):  # type: ignore
                mk = _to_modified_key(key)
                if mk:
                    self._raw_key_q.put(mk)
            with keyboard.Listener(on_press=on_press) as listener:  # type: ignore
                listener.join()
        self._listener_thread = threading.Thread(
            target=_listen, name="WinstonKeyListener", daemon=True
        )
        self._listener_thread.start()
def _to_modified_key(key_obj):  # type: ignore
    try:
        from pynput import keyboard  # type: ignore
    except ImportError:
        return None
    if isinstance(key_obj, keyboard.KeyCode):  # type: ignore
        base = key_obj.char or ""
    else:
        base = str(key_obj).split(".")[-1]
    return ModifiedKey(key=base)
# anchor scaffold