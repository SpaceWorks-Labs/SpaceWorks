"""Gunicorn worker recycling for prometheus-client's shared worker directory."""
import os


def child_exit(server, worker):
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess
        multiprocess.mark_process_dead(worker.pid)


def on_starting(server):
    # Called once by a fresh master before importing the WSGI app. Never use --preload.
    # emptyDir survives a container restart, so old process files must be retired.
    directory = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if directory:
        import re
        from pathlib import Path
        path = Path(directory)
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.is_symlink():
            raise RuntimeError("Metrics directory must not be a symlink.")
        for child in path.iterdir():
            if re.fullmatch(r"(?:counter|histogram|summary|gauge_[a-z]+)_[0-9]+\.db", child.name):
                child.unlink()
