#!/usr/bin/env python3
"""Offline stand-in for the GitHub release provider, used only by install-rehearsal.sh.

It serves source trees from local directories as published `vX.Y.Z-main.<run>.<sha12>`
releases over HTTPS for api.github.com, raw.githubusercontent.com and github.com (the
rehearsal points those names at 127.0.0.1 and trusts a throwaway CA). Two paths are served:
  - release ASSETS (decision 232): /releases/latest redirect and /releases/download/<tag>/
    install.sh, spaceworks-<version>.tar.gz, release.json and SHA256SUMS, built by the tree's
    own scripts/release-assets.sh exactly as the release workflow builds them (a tree that
    predates it serves none; there is no cosign signature - the installer skips it when
    cosign is absent, as in the rehearsal host);
  - the source-tree API (releases, commits, git trees, archives) that update.sh and
    release-fetch.py still use for later updates.
Nothing here is shipped or used by an install.

  version DIR:RUN[:SHA12[:MODES]]      print the version that directory is served as
  serve --cert C --key K --repo O/R --release DIR:RUN[:SHA12[:MODES]] [--release ...]

MODES is optional `git ls-files -s` output (git's exec bits for a Windows working tree).
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import sys
import tarfile


def load_modes(path):
    """`git ls-files -s` output: '<mode> <object> <stage>\\t<path>' per line."""
    modes = {}
    if path:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            meta, _, name = line.partition("\t")
            if name:
                modes[name] = meta.split()[0]
    return modes


def blobs_for(root, modes):
    blobs = []
    for file in sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink()):
        relative = file.relative_to(root).as_posix()
        raw = file.read_bytes()
        if modes:  # a Windows working tree has no reliable exec bit: git's index decides
            mode = modes.get(relative) or ("100755" if relative.endswith(".sh") else "100644")
        else:  # extracted from `git archive`, which carries git's modes
            mode = "100755" if file.stat().st_mode & 0o111 else "100644"
        mode = mode if mode in {"100644", "100755"} else "100644"
        blobs.append({"path": relative, "type": "blob", "mode": mode, "size": len(raw),
                      "sha": hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()})
    return blobs


def commit_for(blobs, sha12):
    digest = hashlib.sha1(json.dumps(blobs, sort_keys=True).encode()).hexdigest()
    return (sha12 + digest)[:40] if sha12 else digest


class Release:
    """One served release. SPEC is DIR:RUN[:SHA12[:MODES]]; SHA12 pins a real tag's suffix."""

    def __init__(self, spec, build_archive=True):
        directory, run, sha12, modes = (spec.split(":") + ["", ""])[:4]
        self.root = Path(directory)
        self.run = int(run)
        self.blobs = blobs_for(self.root, load_modes(modes))
        self.commit = commit_for(self.blobs, sha12)
        base = (self.root / "VERSION").read_text(encoding="utf-8").strip()
        self.version = f"{base}-main.{self.run}.{self.commit[:12]}"
        self.assets = {}
        if not build_archive:
            return
        self.build_assets()
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for blob in self.blobs:
                archive.add(self.root / blob["path"], arcname=f"release/{blob['path']}", recursive=False)
        self.archive = buffer.getvalue()


def build_assets(self):
    script = self.root / "scripts/release-assets.sh"
    if not script.is_file():
        return
    for blob in self.blobs:  # a Windows working tree has no reliable exec bits: git's index decides
        os.chmod(self.root / blob["path"], 0o755 if blob["mode"] == "100755" else 0o644)
    out = Path(tempfile.mkdtemp(prefix="assets-"))
    subprocess.run(["bash", str(script), self.version, self.commit, str(out)], check=True,
                   stdout=subprocess.DEVNULL)
    self.assets = {item.name: item.read_bytes() for item in out.iterdir()}


Release.build_assets = build_assets


def make_handler(repo, releases):
    by_tag = {f"v{r.version}": r for r in releases}
    by_commit = {r.commit: r for r in releases}

    def describe(release):
        # Later runs publish later, so "latest" is the highest run number, as on GitHub.
        published = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=release.run)
        return {"tag_name": f"v{release.version}", "draft": False, "prerelease": False,
                "published_at": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "html_url": f"https://github.com/{repo}/releases/tag/v{release.version}"}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            host = self.headers.get("Host", "").split(":")[0]
            path = self.path.split("?", 1)[0]
            prefix = f"/repos/{repo}/"
            body = None
            if host == "api.github.com" and path.startswith(prefix):
                rest = path[len(prefix):]
                if rest == "releases":
                    ordered = sorted(releases, key=lambda r: -r.run)
                    body = json.dumps([describe(r) for r in ordered]).encode()
                elif rest.startswith("releases/tags/") and rest[14:] in by_tag:
                    body = json.dumps(describe(by_tag[rest[14:]])).encode()
                elif rest.startswith("commits/") and rest[8:] in by_tag:
                    body = json.dumps({"sha": by_tag[rest[8:]].commit}).encode()
                elif rest.startswith("git/trees/") and rest[10:] in by_commit:
                    body = json.dumps({"truncated": False, "tree": by_commit[rest[10:]].blobs}).encode()
            elif host == "raw.githubusercontent.com" and path.startswith(f"/{repo}/"):
                commit, _, name = path[len(repo) + 2:].partition("/")
                release = by_commit.get(commit)
                if release and any(blob["path"] == name for blob in release.blobs):
                    body = (release.root / name).read_bytes()
            elif host == "github.com" and path == f"/{repo}/releases/latest":
                with_assets = [r for r in releases if r.assets]
                if with_assets:
                    newest = max(with_assets, key=lambda r: r.run)
                    self.send_response(302)
                    self.send_header("Location", f"https://github.com/{repo}/releases/tag/v{newest.version}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            elif host == "github.com" and path.startswith(f"/{repo}/releases/latest/download/"):
                with_assets = [r for r in releases if r.assets]
                if with_assets:
                    newest = max(with_assets, key=lambda r: r.run)
                    self.send_response(302)
                    self.send_header("Location", f"https://github.com/{repo}/releases/download/v{newest.version}/"
                                     + path.rsplit("/", 1)[1])
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            elif host == "github.com" and path.startswith(f"/{repo}/releases/download/"):
                tag, _, asset = path[len(repo) + 20:].partition("/")
                release = by_tag.get(tag)
                body = release.assets.get(asset) if release else None
            elif host == "github.com" and path.startswith(f"/{repo}/archive/") and path.endswith(".tar.gz"):
                release = by_commit.get(path.rsplit("/", 1)[1][:-7])
                body = release.archive if release else None
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            sys.stderr.write("fixture: " + fmt % args + "\n")

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("version").add_argument("release")
    serve = commands.add_parser("serve")
    serve.add_argument("--cert", required=True)
    serve.add_argument("--key", required=True)
    serve.add_argument("--repo", required=True)
    serve.add_argument("--release", action="append", required=True)
    serve.add_argument("--port", type=int, default=443)
    args = parser.parse_args()
    if args.command == "version":
        print(Release(args.release, build_archive=False).version)
        return
    releases = [Release(spec) for spec in args.release]
    for release in releases:
        print(f"fixture: serving v{release.version} from {release.root}", file=sys.stderr, flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.repo, releases))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.cert, args.key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
