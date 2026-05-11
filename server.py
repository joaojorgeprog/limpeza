#!/usr/bin/env python3
"""
Servidor local — Plano de Limpeza da Freguesia de Minde
========================================================
Instalar dependências (uma vez):
    pip install flask

Iniciar:
    python server.py

Aceder no browser:
    http://localhost:5000              (este computador)
    http://192.168.x.x:5000           (outros dispositivos na mesma rede WiFi)
"""

import json
import sqlite3
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from flask import Flask, request, jsonify, send_from_directory, abort
except ImportError:
    print("\n❌ Flask não está instalado.")
    print("   Execute este comando e tente novamente:\n")
    print("       pip install flask\n")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
BASE_DIR  = Path(__file__).parent.resolve()
DB_PATH   = BASE_DIR / "limpeza.db"
PORT      = 5000
HOST      = "0.0.0.0"   # aceita ligações de toda a rede local

app = Flask(__name__, static_folder=str(BASE_DIR))


# ---------------------------------------------------------------------------
# Base de dados — inicialização
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # melhor concorrência
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                team        TEXT    NOT NULL,
                zone_id     INTEGER NOT NULL,
                hours       REAL    NOT NULL,
                observations TEXT   DEFAULT '',
                streets_completed TEXT DEFAULT '[]',
                photos      TEXT    DEFAULT '[]',
                created_at  TEXT    NOT NULL,
                edited_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS urgencias (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                team        TEXT    NOT NULL,
                zone_id     INTEGER NOT NULL,
                type        TEXT    NOT NULL,
                location    TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                priority    TEXT    NOT NULL DEFAULT 'urgente',
                status      TEXT    NOT NULL DEFAULT 'pendente',
                created_at  TEXT    NOT NULL,
                edited_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '{}'
            );
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def row_to_record(r):
    d = dict(r)
    d["zone"]             = d.pop("zone_id")
    d["streetsCompleted"] = json.loads(d.pop("streets_completed") or "[]")
    d["photos"]           = json.loads(d.get("photos") or "[]")
    return d


def row_to_urgencia(u):
    d = dict(u)
    d["zoneId"]    = d.pop("zone_id")
    d["createdAt"] = d.get("created_at", "")
    return d


# ---------------------------------------------------------------------------
# Rotas — Página principal
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR), "index.html")


# ---------------------------------------------------------------------------
# Rota — Carregar todos os dados de uma vez (startup da app)
# ---------------------------------------------------------------------------
@app.route("/api/data")
def get_all_data():
    with get_db() as conn:
        records   = [row_to_record(r)   for r in conn.execute(
            "SELECT * FROM records ORDER BY created_at DESC").fetchall()]
        urgencias = [row_to_urgencia(u) for u in conn.execute(
            "SELECT * FROM urgencias ORDER BY created_at DESC").fetchall()]

        def get_config(key):
            row = conn.execute(
                "SELECT value FROM config WHERE key=?", (key,)).fetchone()
            return json.loads(row["value"]) if row else {}

        return jsonify({
            "records":          records,
            "urgencias":        urgencias,
            "zonesOverride":    get_config("zonesOverride"),
            "scheduleOverride": get_config("scheduleOverride"),
        })


# ---------------------------------------------------------------------------
# Rotas — Registos de limpeza
# ---------------------------------------------------------------------------
@app.route("/api/records", methods=["POST"])
def add_record():
    d   = request.get_json(force=True)
    now = now_iso()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO records
               (date, team, zone_id, hours, observations,
                streets_completed, photos, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (d["date"], d["team"], int(d["zone"]), float(d["hours"]),
             d.get("observations", ""),
             json.dumps(d.get("streetsCompleted", [])),
             json.dumps(d.get("photos", [])),
             now))
        conn.commit()
        return jsonify({"id": cur.lastrowid, "created_at": now}), 201


@app.route("/api/records/<int:rid>", methods=["PUT"])
def update_record(rid):
    d   = request.get_json(force=True)
    now = now_iso()
    with get_db() as conn:
        rows = conn.execute(
            """UPDATE records
               SET date=?, team=?, zone_id=?, hours=?, observations=?,
                   streets_completed=?, photos=?, edited_at=?
               WHERE id=?""",
            (d["date"], d["team"], int(d["zone"]), float(d["hours"]),
             d.get("observations", ""),
             json.dumps(d.get("streetsCompleted", [])),
             json.dumps(d.get("photos", [])),
             now, rid)).rowcount
        conn.commit()
        if not rows:
            abort(404)
        return jsonify({"ok": True, "edited_at": now})


@app.route("/api/records/<int:rid>", methods=["DELETE"])
def delete_record(rid):
    with get_db() as conn:
        conn.execute("DELETE FROM records WHERE id=?", (rid,))
        conn.commit()
        return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Rotas — Urgências
# ---------------------------------------------------------------------------
@app.route("/api/urgencias", methods=["POST"])
def add_urgencia():
    d   = request.get_json(force=True)
    now = now_iso()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO urgencias
               (date, team, zone_id, type, location,
                description, priority, status, created_at)
               VALUES (?,?,?,?,?,?,?,'pendente',?)""",
            (d["date"], d["team"], int(d["zoneId"]), d["type"],
             d["location"], d.get("description", ""), d["priority"], now))
        conn.commit()
        return jsonify({"id": cur.lastrowid, "created_at": now}), 201


@app.route("/api/urgencias/<int:uid>", methods=["PUT"])
def update_urgencia(uid):
    d   = request.get_json(force=True)
    now = now_iso()
    with get_db() as conn:
        rows = conn.execute(
            """UPDATE urgencias
               SET type=?, location=?, description=?,
                   priority=?, status=?, edited_at=?
               WHERE id=?""",
            (d["type"], d["location"], d.get("description", ""),
             d["priority"], d["status"], now, uid)).rowcount
        conn.commit()
        if not rows:
            abort(404)
        return jsonify({"ok": True, "edited_at": now})


# ---------------------------------------------------------------------------
# Rotas — Configuração (zonas e calendário)
# ---------------------------------------------------------------------------
@app.route("/api/config/<key>", methods=["PUT"])
def set_config(key):
    if key not in ("zonesOverride", "scheduleOverride"):
        abort(400)
    value = request.get_json(force=True)
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?,?)",
            (key, json.dumps(value)))
        conn.commit()
        return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Rotas — Exportar / Importar backup completo
# ---------------------------------------------------------------------------
@app.route("/api/export")
def export_data():
    with get_db() as conn:
        records   = [row_to_record(r)   for r in conn.execute(
            "SELECT * FROM records ORDER BY created_at DESC").fetchall()]
        urgencias = [row_to_urgencia(u) for u in conn.execute(
            "SELECT * FROM urgencias ORDER BY created_at DESC").fetchall()]

        def get_cfg(key):
            row = conn.execute(
                "SELECT value FROM config WHERE key=?", (key,)).fetchone()
            return json.loads(row["value"]) if row else {}

        return jsonify({
            "exportDate":      now_iso(),
            "version":         "3.0-sqlite",
            "records":         records,
            "urgencias":       urgencias,
            "zonesOverride":   get_cfg("zonesOverride"),
            "scheduleOverride": get_cfg("scheduleOverride"),
        })


@app.route("/api/import", methods=["POST"])
def import_data():
    d = request.get_json(force=True)
    with get_db() as conn:
        conn.execute("DELETE FROM records")
        conn.execute("DELETE FROM urgencias")

        for r in d.get("records", []):
            conn.execute(
                """INSERT INTO records
                   (id, date, team, zone_id, hours, observations,
                    streets_completed, photos, created_at, edited_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (r.get("id"), r["date"], r["team"],
                 int(r.get("zone", 0)), float(r["hours"]),
                 r.get("observations", ""),
                 json.dumps(r.get("streetsCompleted", [])),
                 json.dumps(r.get("photos", [])),
                 r.get("created_at", now_iso()),
                 r.get("edited_at")))

        for u in d.get("urgencias", []):
            conn.execute(
                """INSERT INTO urgencias
                   (id, date, team, zone_id, type, location, description,
                    priority, status, created_at, edited_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (u.get("id"), u["date"], u["team"],
                 int(u.get("zoneId", 0)), u["type"], u["location"],
                 u.get("description", ""), u["priority"],
                 u.get("status", "pendente"),
                 u.get("createdAt", u.get("created_at", now_iso())),
                 u.get("edited_at")))

        for key in ("zonesOverride", "scheduleOverride"):
            if key in d:
                conn.execute(
                    "INSERT OR REPLACE INTO config (key, value) VALUES (?,?)",
                    (key, json.dumps(d[key])))

        conn.commit()
        return jsonify({
            "ok":       True,
            "records":  len(d.get("records",  [])),
            "urgencias": len(d.get("urgencias", [])),
        })


# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()

    # Detectar IP local para mostrar o endereço de rede
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    print()
    print("=" * 60)
    print("  🧹 Plano de Limpeza — Freguesia de Minde")
    print("=" * 60)
    print(f"  ▶  Este computador : http://localhost:{PORT}")
    print(f"  ▶  Outros devices  : http://{local_ip}:{PORT}")
    print(f"  ▶  Base de dados   : {DB_PATH}")
    print(f"  ▶  Para parar      : Ctrl + C")
    print("=" * 60)
    print()

    app.run(host=HOST, port=PORT, debug=False)
