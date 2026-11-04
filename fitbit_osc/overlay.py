# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 hemiize - https://github.com/Hemiize/fitbit-vrchat-osc (credit required, see NOTICE)
"""Kleine lokale Webseite mit dem Puls, als Browserquelle für OBS. Lauscht nur auf 127.0.0.1."""
from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Heart rate</title>
<style>
html,body{margin:0;background:transparent;overflow:hidden}
#hr{display:inline-flex;align-items:center;gap:.25em;padding:.1em .2em;
  font:700 var(--size,64px)/1 "Segoe UI",system-ui,sans-serif;color:var(--color,#fff);
  text-shadow:0 0 .1em rgba(0,0,0,.7);transition:opacity .4s}
#hr.off{opacity:.35}
#heart{color:var(--heart,#e12d46);display:inline-block}
@keyframes beat{0%{transform:scale(1)}15%{transform:scale(1.22)}30%{transform:scale(1)}100%{transform:scale(1)}}
</style></head>
<body><div id="hr" class="off"><span id="heart">&#9829;</span><span id="bpm">--</span></div>
<script>
const q = new URLSearchParams(location.search), root = document.getElementById("hr");
for (const k of ["size", "color", "heart"]) {
  const v = q.get(k);
  if (v) root.style.setProperty("--" + k, k === "size" ? parseInt(v, 10) + "px" : v);
}
const heart = document.getElementById("heart"), bpmEl = document.getElementById("bpm");
let shown = 0;
async function poll() {
  try {
    const d = await (await fetch("hr.json", {cache: "no-store"})).json();
    if (d.active && d.bpm) {
      bpmEl.textContent = d.bpm;
      root.classList.remove("off");
      if (d.bpm !== shown) { heart.style.animation = "beat " + (60 / d.bpm) + "s infinite"; shown = d.bpm; }
    } else {
      bpmEl.textContent = "--"; root.classList.add("off"); heart.style.animation = "none"; shown = 0;
    }
  } catch (e) { root.classList.add("off"); }
}
poll(); setInterval(poll, 1000);
</script></body></html>
"""


class Overlay:
    def __init__(self, snapshot: Callable[[], dict], port: int):
        self.snapshot = snapshot
        self.port = port
        self.server: ThreadingHTTPServer | None = None

    @property
    def url(self) -> str:
        port = self.server.server_address[1] if self.server else self.port
        return f"http://127.0.0.1:{port}/"

    def start(self) -> str:
        snapshot = self.snapshot

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path in ("/", "/index.html"):
                    body, ctype = PAGE.encode("utf-8"), "text/html; charset=utf-8"
                elif path == "/hr.json":
                    body, ctype = json.dumps(snapshot()).encode(), "application/json"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # kein Zugriffslog
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.url

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    @property
    def running(self) -> bool:
        return self.server is not None
