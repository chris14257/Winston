import time
from winston.anchor import Anchor, ModifiedKey
from winston.applets.editor import EditorApplet
def test_typing_hi():
    """Type 'hi' and press Enter; buffer should contain one line 'hi'."""
    anchor = Anchor()
    anchor.register_applet("editor", EditorApplet)
    anchor.activate("editor")
    editor = anchor.applets["editor"]
    # Simulate typing “hi” then Enter
    for ch in "hi":
        editor.key_q.put(ModifiedKey(key=ch))
    editor.key_q.put(ModifiedKey(key="enter"))
    # Give the background thread time to process the keystrokes
    time.sleep(0.1)
    assert editor.lines()[0] == "hi"