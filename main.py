from flask import Flask, render_template, request, jsonify
import threading
import time
import traceback
import requests

app = Flask(__name__)

# --- CONFIGURATION ---
SITE_URL = "https://ffbot-likho-5.onrender.com"  # Apna URL yahan check kar lena

# Data Storage
ALL_BOTS = {}

# --- BOT LOGIC IMPORT ---
try:
    from bot_logic import FF_CLIENT
    print("[SYSTEM] Bot Logic Loaded Successfully!")
except Exception as e:
    print(f"[ERROR] Logic load failed: {e}")
    def FF_CLIENT(u, p): return None

# --- AUTO WAKE SYSTEM ---
def keep_alive():
    while True:
        try:
            time.sleep(60) # Har 1 minute me ping karega (Aggressive Keep-Alive)
            if "YOUR_RENDER_URL" not in SITE_URL:
                requests.get(SITE_URL)
                print("[PING] Keeping Server Awake...")
        except: pass
threading.Thread(target=keep_alive, daemon=True).start()

# --- WORKER FUNCTION ---
def background_worker(uid, duration_seconds):
    global ALL_BOTS
    
    try:
        print(f"[BOT START] {uid}")
        ALL_BOTS[uid]['status'] = 'RUNNING'
        ALL_BOTS[uid]['active'] = True
        
        # --- MAJOR FIX: Connection ko variable me store kiya ---
        # Pehle ye line thi: FF_CLIENT(uid, ALL_BOTS[uid]['password'])
        # Ab ye hum connection ko 'client' variable me hold kar rahen hain
        client_instance = FF_CLIENT(uid, ALL_BOTS[uid]['password'])
        
        # Connection object ko global dictionary me save kar lo taaki delete na ho
        ALL_BOTS[uid]['client_ref'] = client_instance
        # -----------------------------------------------------
        
        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            if ALL_BOTS[uid].get('stop_req'):
                print(f"[BOT STOPPED] {uid} by User")
                break
            
            # Har 10 second me check karo ki kya bot zinda hai?
            # (Agar bot_logic me koi 'is_connected' function ho to use kar sakte hain)
            
            ALL_BOTS[uid]['elapsed'] = int(time.time() - start_time)
            time.sleep(1)
            
    except Exception as e:
        print(f"[ERROR] {uid}: {e}")
    finally:
        if uid in ALL_BOTS:
            ALL_BOTS[uid]['status'] = 'OFF'
            ALL_BOTS[uid]['active'] = False
            # Memory clear karo
            if 'client_ref' in ALL_BOTS[uid]:
                del ALL_BOTS[uid]['client_ref']
            print(f"[BOT END] {uid} moved to OFF section")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_bot():
    name = request.form.get('name')
    uid = request.form.get('uid')
    password = request.form.get('password')
    raw_time = request.form.get('time')
    unit = request.form.get('unit')

    if not uid or not password: return jsonify({"status": "error", "message": "UID/Pass Missing!"})
    if uid in ALL_BOTS and ALL_BOTS[uid]['active']:
        return jsonify({"status": "error", "message": "Ye Bot pehle se RUNNING hai!"})

    try:
        duration = int(raw_time)
        if unit == "min": duration *= 60
        elif unit == "hours": duration *= 3600
        elif unit == "days": duration *= 86400
        elif unit == "permanent": duration = 999999999
    except:
        return jsonify({"status": "error", "message": "Invalid Time!"})

    ALL_BOTS[uid] = {
        'name': name if name else uid,
        'uid': uid,
        'password': password,
        'status': 'STARTING...',
        'active': True,
        'stop_req': False,
        'elapsed': 0,
        'total_time': duration
    }

    t = threading.Thread(target=background_worker, args=(uid, duration))
    t.daemon = True
    t.start()
    
    return jsonify({"status": "success", "message": f"Bot {uid} Started!"})

@app.route('/stop', methods=['POST'])
def stop_bot():
    uid = request.form.get('uid')
    if uid in ALL_BOTS and ALL_BOTS[uid]['active']:
        ALL_BOTS[uid]['stop_req'] = True
        return jsonify({"status": "success", "message": "Stopping..."})
    return jsonify({"status": "error", "message": "Bot already OFF"})

@app.route('/active_bots')
def get_active_bots():
    # Frontend ko bhejte waqt 'client_ref' object hata dete hain (kyunki wo JSON nahi ban sakta)
    display_data = {}
    for uid, data in ALL_BOTS.items():
        # Copy data without the complex client object
        display_data[uid] = {k:v for k,v in data.items() if k != 'client_ref'}
    return jsonify(display_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
