from flask import Flask, render_template, jsonify
import os

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/health")
def health():
    installed = os.path.exists("/etc/jibsz-tunnel/installed.lock")
    return jsonify({"status": "ok", "installed": installed})

if __name__ == "__main__":
    port = 8488
    if os.path.exists("/etc/jibsz-tunnel/panel_port.conf"):
        try:
            port = int(open("/etc/jibsz-tunnel/panel_port.conf").read().strip())
        except Exception:
            port = 8488
    app.run(host="0.0.0.0", port=port)
