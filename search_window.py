from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import tkinter as tk
from tkinter import messagebox, ttk

from file_actions import open_path
from tracks import Track, local_files, search_tracks


class SearchWindow:
    def __init__(self, parent, folder, track=None, files=None, on_delete=None):
        self.window = tk.Toplevel(parent)
        self.window.title("Audio Search")
        self.window.geometry("1000x500")
        self.window.minsize(600, 320)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.folder = Path(folder).absolute()
        self.files = files
        self.on_delete = on_delete
        self.results = []
        self.timer = None
        track = track or Track("", "")
        self.title = tk.StringVar(self.window, value=track.title)
        self.artist = tk.StringVar(self.window, value=track.artist)
        self.status = tk.StringVar(self.window)

        top = ttk.Frame(self.window, padding=10)
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate((("Title", self.title), ("Artist", self.artist))):
            ttk.Label(top, text=label).grid(row=row, column=0, sticky="w", pady=4)
            entry = ttk.Entry(top, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", padx=8)
            entry.bind("<Return>", lambda event: self.search())
        self.search_button = ttk.Button(top, text="Search", command=self.search)
        self.search_button.grid(row=0, column=2, sticky="ew")

        frame = ttk.Frame(self.window, padding=(10, 0))
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        columns = [("score", "Rank score", 85), ("title", "Title score", 85),
                   ("artist", "Artist bonus", 95), ("file", "File", 280), ("path", "Relative path", 440)]
        self.tree = ttk.Treeview(frame, columns=[column[0] for column in columns], show="headings", selectmode="browse")
        for column, label, width in columns:
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=70)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self.update_actions)
        self.tree.bind("<Double-1>", lambda event: self.open_file())

        bottom = ttk.Frame(self.window, padding=10)
        bottom.pack(fill="x")
        bottom.columnconfigure(0, weight=1)
        self.actions = []
        for index, (label, command) in enumerate((("Delete", self.delete_file), ("Open folder", self.open_folder),
                                                 ("Open", self.open_file))):
            button = ttk.Button(bottom, text=label, command=command, state="disabled")
            button.grid(row=0, column=3 - index, sticky="e", padx=(6, 0))
            self.actions.append(button)
        ttk.Label(bottom, textvariable=self.status, wraplength=450).grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))
        if files is None:
            self.search_button.configure(state="disabled")
            self.status.set("Scanning audio folder...")
            self.queue = Queue()
            Thread(target=self.scan, daemon=True).start()
            self.poll()
        else:
            self.search()

    def scan(self):
        try:
            self.queue.put(local_files(self.folder))
        except Exception as error:
            self.queue.put(error)

    def poll(self):
        self.timer = None
        try:
            result = self.queue.get_nowait()
        except Empty:
            self.timer = self.window.after(100, self.poll)
            return
        self.search_button.configure(state="normal")
        if isinstance(result, Exception):
            self.status.set("Scan failed.")
            messagebox.showerror("Cannot search folder", str(result), parent=self.window)
        else:
            self.files = result
            self.search()

    def search(self):
        if self.files is None:
            return
        self.results = search_tracks(Track(self.artist.get().strip(), self.title.get().strip()), self.files)
        self.tree.delete(*self.tree.get_children())
        for index, result in enumerate(self.results):
            self.tree.insert("", "end", iid=str(index), values=(result.score, result.title_score, result.artist_score,
                                                                Path(result.path).name, result.path))
        self.status.set(f"{len(self.results)} results / {len(self.files)} audio files")
        self.update_actions()

    def selected_path(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return self.folder / self.results[int(selection[0])].path

    def update_actions(self, event=None):
        state = "normal" if self.tree.selection() else "disabled"
        for button in self.actions:
            button.configure(state=state)

    def open_file(self):
        self.open_selected(False)

    def open_folder(self):
        self.open_selected(True)

    def open_selected(self, folder):
        path = self.selected_path()
        if path is None:
            return
        try:
            open_path(path.parent if folder else path)
        except OSError as error:
            messagebox.showerror("Cannot open path", str(error), parent=self.window)

    def delete_file(self):
        path = self.selected_path()
        if path is None:
            return
        if not messagebox.askyesno("Delete audio file", f"Permanently delete this file?\n\n{path}",
                                  parent=self.window, default="no", icon="warning"):
            return
        try:
            path.unlink()
        except OSError as error:
            messagebox.showerror("Cannot delete file", str(error), parent=self.window)
            return
        relative = path.relative_to(self.folder).as_posix()
        self.files[:] = [file for file in self.files if file.path != relative]
        self.search()
        if self.on_delete:
            self.on_delete()

    def close(self):
        if self.timer is not None:
            self.window.after_cancel(self.timer)
        self.window.destroy()