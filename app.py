from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from export import write_playlist
from history import History
from providers import load_playlist, provider_for
from search_window import SearchWindow
from tracks import local_files, match_track


class PlaylistApp:
    def __init__(self, root, history=None):
        self.root = root
        self.history = history if history is not None else History()
        self.results = Queue()
        self.busy = False
        self.export_entries = []
        self.export_folder = None
        self.files = []
        self.loaded_playlist = None
        self.loaded_url = None
        self.search_window = None
        self.url = tk.StringVar(root)
        self.folder = tk.StringVar(root)
        self.status = tk.StringVar(root, value="")
        root.title("Playlist Compare")
        root.geometry("1000x600")
        root.minsize(620, 360)
        root.protocol("WM_DELETE_WINDOW", self.close)

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Playlist URL").grid(row=0, column=0, sticky="w")
        self.playlists = ttk.Combobox(top, textvariable=self.url)
        self.playlists.grid(row=0, column=1, sticky="ew", padx=8)
        self.playlists.bind("<<ComboboxSelected>>", self.select_playlist)
        self.playlists.bind("<Return>", lambda event: self.load())
        self.load_button = ttk.Button(top, text="Load", command=self.load)
        self.load_button.grid(row=0, column=2, sticky="ew")
        self.reload_button = ttk.Button(top, text="Force Reload", command=self.reload_playlist)
        self.reload_button.grid(row=0, column=3, sticky="ew", padx=(8, 0))
        ttk.Label(top, text="Audio folder").grid(row=1, column=0, sticky="w", pady=8)
        self.folder_entry = ttk.Entry(top, textvariable=self.folder)
        self.folder_entry.grid(row=1, column=1, sticky="ew", padx=8)
        self.browse_button = ttk.Button(top, text="Browse", command=self.browse)
        self.browse_button.grid(row=1, column=2, sticky="ew")
        self.rescan_button = ttk.Button(top, text="Rescan Files", command=self.rescan_files, state="disabled")
        self.rescan_button.grid(row=1, column=3, sticky="ew", padx=(8, 0))

        frame = ttk.Frame(root, padding=(10, 0, 10, 0))
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        columns = [("status", "Status", 90), ("artist", "Artist", 220),
                   ("title", "Track", 300), ("file", "Local file", 350)]
        self.tree = ttk.Treeview(frame, columns=[column[0] for column in columns], show="headings")
        for column, label, width in columns:
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=80)
        self.tree.tag_configure("missing", foreground="#b42318")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<Double-1>", lambda event: self.search())

        bottom = ttk.Frame(root, padding=10)
        bottom.pack(fill="x")
        self.export_button = ttk.Button(bottom, text="Export M3U", command=self.export, state="disabled")
        self.export_button.pack(side="right")
        self.search_button = ttk.Button(bottom, text="Search Files", command=self.search)
        self.search_button.pack(side="right", padx=(6, 0))
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=100)
        self.progress.pack(side="right", padx=8)
        ttk.Label(bottom, textvariable=self.status, wraplength=250).pack(side="left")
        self.refresh_history()
        if self.history.entries:
            entry = self.history.entries[0]
            self.url.set(entry["url"])
            self.folder.set(entry["folder"])

    def refresh_history(self):
        self.playlists.configure(values=[f"{entry['name']} | {entry['url']}" for entry in self.history.entries])

    def select_playlist(self, event=None):
        index = self.playlists.current()
        if index >= 0:
            entry = self.history.entries[index]
            self.url.set(entry["url"])
            self.folder.set(entry["folder"])

    def browse(self):
        folder = filedialog.askdirectory(parent=self.root, initialdir=self.folder.get() or None)
        if folder:
            self.folder.set(folder)

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.playlists, self.folder_entry, self.load_button, self.reload_button,
                       self.browse_button, self.search_button):
            widget.configure(state="disabled" if busy else "normal")
        self.rescan_button.configure(state="normal" if self.loaded_playlist is not None and not busy else "disabled")
        self.export_button.configure(state="normal" if self.export_entries and not busy else "disabled")
        if busy:
            self.progress.start()
        else:
            self.progress.stop()

    def reload_playlist(self):
        self.load(force_reload=True)

    def rescan_files(self):
        if self.loaded_playlist is not None:
            self.load(rescan=True)

    def load(self, *, force_reload=False, rescan=False):
        if self.busy:
            return
        url = self.loaded_url if rescan else self.url.get().strip()
        folder = str(Path(self.folder.get().strip()).expanduser().absolute())
        try:
            provider_for(url)
            if not self.folder.get().strip() or not Path(folder).is_dir():
                raise ValueError("Choose an existing audio folder.")
        except ValueError as error:
            messagebox.showerror("Cannot load playlist", str(error), parent=self.root)
            return
        self.close_search()
        if not rescan:
            self.url.set(url)
        self.set_busy(True)
        self.status.set("Rescanning files..." if rescan else "Reloading playlist..." if force_reload else "Loading playlist...")
        playlist = self.loaded_playlist if rescan else None
        Thread(target=self.compare, args=(url, folder, playlist, force_reload), daemon=True).start()
        self.poll(url, folder)

    def compare(self, url, folder, playlist=None, force_reload=False):
        try:
            files = local_files(folder)
            if playlist is None:
                playlist = load_playlist(url, force_reload=force_reload)
            rows = [(track, match_track(track, files)) for track in playlist.tracks]
            self.results.put((playlist, rows, files))
        except Exception as error:
            self.results.put(error)

    def poll(self, url, folder):
        try:
            result = self.results.get_nowait()
        except Empty:
            self.root.after(100, self.poll, url, folder)
            return
        if isinstance(result, Exception):
            self.set_busy(False)
            self.status.set("Load failed.")
            messagebox.showerror("Cannot load playlist", str(result), parent=self.root)
            return
        playlist, rows, self.files = result
        self.loaded_playlist = playlist
        self.loaded_url = url
        self.export_folder = Path(folder)
        self.render_results(rows)
        try:
            self.history.remember(url, playlist.name, folder)
            self.refresh_history()
        except OSError as error:
            messagebox.showwarning("History not saved", str(error), parent=self.root)

    def render_results(self, rows=None):
        if rows is None:
            rows = [(track, match_track(track, self.files)) for track in self.loaded_playlist.tracks]
        self.export_entries = [(track, self.export_folder / match) for track, match in rows if match]
        self.set_busy(False)
        self.tree.delete(*self.tree.get_children())
        for index, (track, match) in enumerate(rows):
            self.tree.insert("", "end", iid=str(index),
                             values=("FOUND" if match else "MISSING", track.artist, track.title, match or ""),
                             tags=("found" if match else "missing",))
        found = sum(bool(match) for track, match in rows)
        summary = f"{found} found, {len(rows) - found} missing"
        if self.loaded_playlist.skipped:
            summary += f", {self.loaded_playlist.skipped} unavailable"
        self.status.set(summary)

    def search(self):
        if self.busy:
            return
        selection = self.tree.selection()
        track = self.loaded_playlist.tracks[int(selection[0])] if selection and self.loaded_playlist else None
        folder = self.export_folder if track else Path(self.folder.get().strip()).expanduser().absolute()
        if not folder or not folder.is_dir() or (track is None and not self.folder.get().strip()):
            messagebox.showerror("Cannot search folder", "Choose an existing audio folder.", parent=self.root)
            return
        shared = self.loaded_playlist is not None and folder == self.export_folder
        self.close_search()
        self.search_window = SearchWindow(self.root, folder, track, self.files if shared else None,
                                          self.render_results if shared else None)

    def close_search(self):
        if self.search_window and self.search_window.window.winfo_exists():
            self.search_window.close()
        self.search_window = None

    def close(self):
        self.close_search()
        self.root.destroy()

    def export(self):
        if self.busy or not self.export_entries:
            return
        destination = filedialog.asksaveasfilename(
            parent=self.root, title="Export Mixxx playlist", initialdir=str(self.export_folder),
            initialfile="playlist.m3u8", defaultextension=".m3u8",
            filetypes=[("M3U8 playlist", "*.m3u8"), ("M3U playlist", "*.m3u")],
        )
        if not destination:
            return
        try:
            count = write_playlist(destination, self.export_entries)
        except (OSError, ValueError) as error:
            messagebox.showerror("Cannot export playlist", str(error), parent=self.root)
            return
        self.status.set(f"Exported {count} tracks to {Path(destination).name}.")


def main():
    root = tk.Tk()
    PlaylistApp(root)
    root.mainloop()