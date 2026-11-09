#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NeuroLoad Web — التحميل من المتصفح على جهازك (127.0.0.1:8752)
نفس محرك NeuroLoad (yt-dlp + ffmpeg) — للاستعمال الشخصي / Creative Commons فقط.
لا يوزع ولا يخبئ أي خدمة عامة — كل التحميلات على الجهاز ديالك.
"""
import json
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime

import imageio_ffmpeg

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
HOST, PORT = "127.0.0.1", 8752

QUALITY = {
    "1080p": "bestvideo[height<=1080]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]",
    "MP3": "bestaudio/best",
}

TASKS = {}
DEFAULT_OUT = os.path.join(os.path.expanduser("~"), "Downloads", "NeuroLoad", "Web")

PAGE = r"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>NeuroLoad Web — on your PC</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='88'>⬇️</text></svg>"/>
<style>
:root{--bg:#070b18;--panel:#151d38;--panel2:#1f2947;--panel3:#262f55;--cyan:#22d3ee;--violet:#8b5cf6;--text:#e8ecfb;--dim:#98a2c6;--green:#34d399;--amber:#fbbf24;--red:#f87171}
*{margin:0;padding:0;box-sizing:border-box}
body{background:radial-gradient(900px 500px at 85% -10%,rgba(139,92,246,.28),transparent 60%),radial-gradient(700px 500px at -10% 35%,rgba(34,211,238,.18),transparent 60%),var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:26px}
.wrap{max-width:880px;margin:0 auto}
header{display:flex;align-items:center;gap:14px;margin-bottom:22px}
.logo{width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,var(--cyan),var(--violet));display:grid;place-items:center;font-size:26px}
h1{font-size:26px;letter-spacing:.4px}
.sub{color:var(--dim);font-size:12px}
.panel{background:var(--panel);border:1px solid var(--panel2);border-radius:18px;padding:18px;margin-bottom:14px;box-shadow:0 18px 40px rgba(0,0,0,.4)}
.label{font-size:11px;color:var(--dim);font-weight:700;letter-spacing:.14em;margin-bottom:8px}
.row{display:flex;gap:10px}
input[type=text]{flex:1;background:#111830;border:1px solid var(--panel3);color:var(--text);padding:13px 15px;border-radius:12px;font-size:13px;outline:none}
input[type=text]:focus{border-color:var(--cyan)}
button{cursor:pointer;border:0;border-radius:12px;font-weight:700;transition:.15s}
.btn-grad{background:linear-gradient(90deg,var(--cyan),var(--violet));color:#071018;padding:13px 22px;font-size:14px}
.btn-grad:hover{filter:brightness(1.08)}
.btn-grad:disabled{background:var(--panel3);color:var(--dim);cursor:not-allowed}
.btn-ghost{background:var(--panel2);color:var(--cyan);padding:12px 16px}
.info{display:flex;gap:16px}
.info img{width:212px;height:119px;object-fit:cover;border-radius:12px;background:#111830}
.info h2{font-size:17px;margin:2px 0 6px}
.info .meta{color:var(--dim);font-size:12px}
.license{display:inline-block;margin-top:8px;font-size:10px;font-weight:700;padding:4px 10px;border-radius:6px}
.cc{color:var(--green);background:rgba(52,211,153,.14)}
.unknown{color:var(--amber);background:rgba(251,191,36,.12)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 12px}
.chip{background:var(--panel2);color:var(--dim);padding:10px 16px;border-radius:10px;font-size:12px;border:1px solid var(--panel3)}
.chip.on{color:var(--cyan);border-color:var(--cyan);background:rgba(34,211,238,.12)}
.chip:hover{color:var(--text)}
.dl{width:100%;height:56px;font-size:17px;border-radius:14px;background:linear-gradient(90deg,var(--cyan),var(--violet));color:#071018;font-weight:800}
.dl:disabled{background:var(--panel3);color:var(--dim)}
.task{background:var(--panel2);border-radius:12px;padding:12px 14px;margin-top:12px}
.task .t1{display:flex;justify-content:space-between;gap:10px;font-size:13px;margin-bottom:8px}
.bar{height:9px;background:var(--panel3);border-radius:5px;overflow:hidden}
.bar>div{height:100%;background:linear-gradient(90deg,var(--cyan),var(--violet));width:0%;transition:width .3s}
.small{color:var(--dim);font-size:10px;margin-top:6px}
.ok{color:var(--green)} .err{color:var(--red)}
footer{text-align:center;color:var(--dim);font-size:10px;margin-top:8px}
.hidden{display:none}
</style></head><body>
<div class="wrap">
  <header>
    <div class="logo">⬇️</div>
    <div><h1>NeuroLoad <span style="color:var(--cyan)">Web</span></h1>
      <div class="sub">Personal use &amp; Creative Commons only · runs on your PC (127.0.0.1) · not a hosted service</div>
    </div>
  </header>

  <div class="panel">
    <div class="label">VIDEO LINK</div>
    <div class="row">
      <input type="text" id="url" placeholder="https://www.youtube.com/watch?v=…"/>
      <button class="btn-ghost" onclick="paste()">Paste</button>
      <button class="btn-grad" id="analyzeBtn" onclick="analyze()">⚡ Analyze</button>
    </div>
  </div>

  <div class="panel hidden" id="infoCard">
    <div class="label">VIDEO PREVIEW</div>
    <div class="info">
      <img id="thumb" alt="thumbnail"/>
      <div>
        <h2 id="title"></h2>
        <div class="meta"><span id="uploader"></span> · <span id="duration"></span></div>
        <div class="license" id="license"></div>
      </div>
    </div>
  </div>

  <div class="panel hidden" id="dlCard">
    <div class="label">FORMAT &amp; QUALITY</div>
    <div class="chips" id="chips"></div>
    <button class="dl" id="downloadBtn" onclick="download()">⬇ Download video · 720p</button>
    <div id="taskArea"></div>
  </div>

  <footer>NeuroLoad Web · yt-dlp engine · For personal use &amp; CC content only — respect YouTube ToS</footer>
</div>
<script>
const Q = ["1080p","720p","480p","360p","MP3"];
let quality = "720p", info = null;

async function paste(){
  try { const t = await navigator.clipboard.readText(); document.getElementById('url').value = t.trim(); }
  catch(e){ alert("Clipboard blocked by browser — paste manually (Ctrl+V)."); }
}

async function analyze(){
  const url = document.getElementById('url').value.trim();
  if(!/^https?:\/\//.test(url)) { alert("Paste a valid http(s) link"); return; }
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = true; btn.textContent = 'Fetching…';
  try {
    const r = await fetch('/api/info', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url})});
    const d = await r.json();
    if(!r.ok) { alert(d.error || 'Failed to fetch info'); return; }
    info = d;
    document.getElementById('title').textContent = d.title || 'Untitled';
    document.getElementById('uploader').textContent = d.uploader || 'Unknown channel';
    document.getElementById('duration').textContent = d.durationStr || '?';
    const lic = document.getElementById('license');
    if(d.license){ lic.textContent = d.license; lic.className = 'license ' + (d.license.toLowerCase().includes('creative commons') ? 'cc':'unknown'); lic.style.display='inline-block'; } else { lic.textContent='License unknown — check rights'; lic.className='license unknown'; }
    const thumb = document.getElementById('thumb');
    if(d.thumbnail){ thumb.src = d.thumbnail; } else { thumb.style.visibility='hidden'; }
    document.getElementById('infoCard').classList.remove('hidden');
    document.getElementById('dlCard').classList.remove('hidden');
    renderChips();
  } catch(e){ alert('Error: ' + e); }
  finally { btn.disabled = false; btn.textContent = '⚡ Analyze'; }
}

function renderChips(){
  const box = document.getElementById('chips'); box.innerHTML='';
  Q.forEach(q=>{
    const b = document.createElement('button');
    b.className = 'chip' + (q===quality?' on':''); b.textContent = q;
    b.onclick = () => { quality = q; renderChips(); document.getElementById('downloadBtn').textContent = (q==='MP3') ? '⬇ Download MP3 Audio' : '⬇ Download video · ' + q; };
    box.appendChild(b);
  });
}

async function download(){
  const url = document.getElementById('url').value.trim();
  const btn = document.getElementById('downloadBtn'); btn.disabled = true; btn.textContent = '⏳ Downloading…';
  const r = await fetch('/api/download', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url, quality})});
  const d = await r.json();
  if(!r.ok){ alert(d.error||'Failed to start'); restoreBtn(); return; }
  poll(d.id);
}

function restoreBtn(){ const btn = document.getElementById('downloadBtn'); btn.disabled=false; btn.textContent = (quality==='MP3')?'⬇ Download MP3 Audio':'⬇ Download video · '+quality; }

function poll(id){
  const area = document.getElementById('taskArea');
  const el = document.createElement('div'); el.className='task';
  el.innerHTML = '<div class="t1"><span id="t-t">Starting…</span><span id="t-p">0%</span></div><div class="bar"><div id="t-bar"></div></div><div class="small" id="t-eta"></div>';
  area.prepend(el);
  const iv = setInterval(async ()=>{
    try {
      const r = await fetch('/api/status?id=' + encodeURIComponent(id));
      const s = await r.json();
      el.querySelector('#t-t').textContent = s.title || 'Downloading…';
      el.querySelector('#t-p').textContent = (s.progress*100).toFixed(1)+'%';
      el.querySelector('#t-bar').style.width = (s.progress*100).toFixed(1)+'%';
      el.querySelector('#t-eta').textContent = s.eta ? 'ETA ' + s.eta : '';
      if(s.status === 'done'){ clearInterval(iv); el.querySelector('#t-eta').innerHTML = '<span class="ok">✓ Saved: '+(s.path||'')+'</span>'; restoreBtn(); }
      else if(s.status === 'failed'){ clearInterval(iv); el.querySelector('#t-eta').innerHTML = '<span class="err">Failed: '+(s.error||'')+'</span>'; restoreBtn(); }
      else if(s.status === 'cancelled'){ clearInterval(iv); el.querySelector('#t-eta').textContent='Cancelled'; restoreBtn(); }
    } catch(e){ /* server busy, keep polling */ }
  }, 700);
}
</script></body></html>
"""


def human_duration(seconds):
    try:
        total = int(seconds or 0)
    except (TypeError, ValueError):
        return "?"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def extract_info(url):
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "durationStr": human_duration(info.get("duration")),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "license": info.get("license"),
        "webpage_url": info.get("webpage_url"),
    }


def newest_in(dir_path, since):
    latest, latest_mtime = None, 0
    for name in os.listdir(dir_path):
        path = os.path.join(dir_path, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime >= since and os.path.isfile(path) and not name.endswith((".part", ".ytdl")):
            if mtime > latest_mtime:
                latest_mtime, latest = mtime, path
    return latest


def run_download(task_id, url, quality):
    TASKS[task_id]["status"] = "downloading"
    TASKS[task_id]["title"] = "Starting…"
    import yt_dlp
    os.makedirs(DEFAULT_OUT, exist_ok=True)
    started = time.time() - 5

    def hook(d):
        t = TASKS[task_id]
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            t["progress"] = (done / total) if total else t.get("progress", 0)
            t["eta"] = re.sub(r"\s+", " ", d.get("_eta_str", "")).strip()
        elif d.get("status") == "finished":
            t["progress"] = 0.99
            t["eta"] = "merging…"

    is_audio = quality == "MP3"
    options = {
        "format": QUALITY.get(quality, QUALITY["720p"]),
        "outtmpl": os.path.join(DEFAULT_OUT, "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "no_mtime": True,
        "concurrent_fragment_downloads": 16,
        "ffmpeg_location": FFMPEG_PATH,
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
    }
    if is_audio:
        options["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}]
    else:
        options["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])
        path = newest_in(DEFAULT_OUT, started)
        TASKS[task_id].update(status="done", progress=1.0, path=path, eta="")
    except Exception as e:
        msg = re.sub(r"\s+", " ", str(e))[:200]
        TASKS[task_id].update(status="failed", error=msg, eta="")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, content_type="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
            return
        if parsed.path == "/api/status":
            task_id = parse_qs(parsed.query).get("id", [""])[0]
            task = TASKS.get(task_id)
            if not task:
                self._json(404, {"error": "unknown task"})
                return
            safe = {k: v for k, v in task.items() if k != "url"}
            self._json(200, safe)
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/info":
            data = self._read_json()
            url = (data.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                self._json(400, {"error": "paste a valid link"})
                return
            try:
                self._json(200, extract_info(url))
            except Exception as e:
                self._json(502, {"error": re.sub(r"\s+", " ", str(e))[:200]})
            return
        if parsed.path == "/api/download":
            data = self._read_json()
            url = (data.get("url") or "").strip()
            quality = data.get("quality") or "720p"
            if quality not in QUALITY:
                quality = "720p"
            if not url.startswith(("http://", "https://")):
                self._json(400, {"error": "paste a valid link"})
                return
            task_id = uuid.uuid4().hex[:12]
            TASKS[task_id] = {"id": task_id, "url": url, "quality": quality, "status": "queued",
                              "progress": 0.0, "eta": "", "title": "…", "path": None, "error": None}
            threading.Thread(target=run_download, args=(task_id, url, quality), daemon=True).start()
            self._json(200, {"id": task_id})
            return
        self._json(404, {"error": "not found"})


def main():
    os.makedirs(DEFAULT_OUT, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"NeuroLoad Web running at http://{HOST}:{PORT}")
    print("Saved files:", DEFAULT_OUT)
    try:
        import webbrowser
        webbrowser.open(f"http://{HOST}:{PORT}")
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
