"""
 HEIC -> JPG  |  Flask Upload & Convert  |  v5.0
"""

import os
import sys
import uuid
import shutil
import threading
import time
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from heic_engine import convert_file, check_heif_support, load_history, undo_last

from flask import Flask, request, jsonify, render_template, send_file

app = Flask(__name__)

TEMP_DIR = Path(app.instance_path) / "converted"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOAD_MAP = {}

def cleanup_old_files():
    while True:
        time.sleep(300)
        now = time.time()
        expired = [p for p in TEMP_DIR.iterdir() if p.is_file() and now - p.stat().st_mtime > 600]
        for p in expired:
            try:
                p.unlink()
            except Exception:
                pass

threading.Thread(target=cleanup_old_files, daemon=True).start()


@app.route("/")
def index():
    ok, msg = check_heif_support()
    return render_template("index.html", heif_ok=ok, heif_msg=msg)


@app.route("/api/check", methods=["GET"])
def api_check():
    ok, msg = check_heif_support()
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/convert", methods=["POST"])
def api_convert():
    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    files = request.files.getlist("files")
    quality = int(request.form.get("quality", 100))

    if not files:
        return jsonify({"error": "No files provided"}), 400

    results = []
    for f in files:
        stem = Path(f.filename).stem
        in_path = TEMP_DIR / f"{uuid.uuid4().hex}.heic"
        in_path.write_bytes(f.read())

        out_path = in_path.with_suffix(".jpg")
        try:
            conv = convert_file(in_path, out_path, quality=quality)
            token = uuid.uuid4().hex
            DOWNLOAD_MAP[token] = out_path
            results.append({
                "name": f"{stem}.jpg",
                "size": out_path.stat().st_size,
                "token": token,
            })
        except Exception as e:
            results.append({"name": f.filename, "error": str(e)})
        finally:
            if in_path.exists():
                in_path.unlink()

    return jsonify({"results": results, "count": len(results)})


@app.route("/api/download/<token>", methods=["GET"])
def api_download(token):
    path = DOWNLOAD_MAP.pop(token, None)
    if not path or not path.exists():
        return jsonify({"error": "File not found or expired"}), 404
    return send_file(str(path), as_attachment=True, download_name=path.name, mimetype="image/jpeg")


@app.route("/api/undo", methods=["POST"])
def api_undo():
    ok, msg = undo_last()
    return jsonify({"success": ok, "message": msg})


@app.route("/api/history", methods=["GET"])
def api_history():
    return jsonify(load_history())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"* Server running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
