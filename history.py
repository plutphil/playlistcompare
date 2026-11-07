import json
import os
from pathlib import Path
import sys
import tempfile


class History:
    def __init__(self, path=None):
        if sys.platform == "win32":
            config = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        else:
            config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        self.path = Path(path) if path is not None else config / "playlistcompare" / "history.json"
        self.entries = []
        try:
            entries = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(entries, list):
                self.entries = [entry for entry in entries if isinstance(entry, dict)
                                and all(isinstance(entry.get(key), str) for key in ("url", "name", "folder"))][:30]
        except (OSError, ValueError):
            pass

    def remember(self, url, name, folder):
        entries = [{"url": url, "name": name, "folder": folder}]
        entries += [entry for entry in self.entries if entry["url"] != url]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(entries[:30], stream, ensure_ascii=False, indent=2)
            temporary.replace(self.path)
            self.entries = entries[:30]
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)