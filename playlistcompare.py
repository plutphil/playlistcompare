from importlib.metadata import distribution
import sys

from app import main


def _restore_windows_streams():
    if sys.platform != "win32":
        return

    import ctypes
    import msvcrt
    import os

    get_std_handle = ctypes.WinDLL("kernel32", use_last_error=True).GetStdHandle
    get_std_handle.argtypes = [ctypes.c_ulong]
    get_std_handle.restype = ctypes.c_void_p
    invalid_handle = ctypes.c_void_p(-1).value
    for name, handle_id in (("stdout", -11), ("stderr", -12)):
        if getattr(sys, name) is None:
            handle = get_std_handle(handle_id)
            if handle not in (None, invalid_handle):
                descriptor = msvcrt.open_osfhandle(handle, os.O_TEXT)
                stream = os.fdopen(descriptor, "w", encoding="utf-8", errors="replace")
                setattr(sys, name, stream)


def run_provider_tool(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if not arguments or arguments[0] != "--_playlistcompare_provider":
        return False
    if len(arguments) < 2 or arguments[1] not in {"spotdl", "yt-dlp"}:
        raise SystemExit("Unknown provider tool.")

    _restore_windows_streams()
    tool = arguments[1]
    package = "yt-dlp" if tool == "yt-dlp" else "spotdl"
    entry_point = next(
        entry for entry in distribution(package).entry_points
        if entry.group == "console_scripts" and entry.name == tool
    )
    sys.argv = [tool, *arguments[2:]]
    raise SystemExit(entry_point.load()())


if __name__ == "__main__":
    if not run_provider_tool():
        main()
