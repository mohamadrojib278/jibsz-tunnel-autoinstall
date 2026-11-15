#!/usr/bin/env python3
"""
JIBSZ TUNNELING / J1BTNL - SSH WEBSOCKET PROXY V3 (ssh_ws_proxy.py)
Author  : Jibsz Tunneling (@admj1btnl)
Support : OpenSSH (127.0.0.1:22) & Dropbear (127.0.0.1:109)
Feature : - Full Bug Host / Bug SNI, Multi-Payload ([split]), CONNECT, GET, POST
          - Menahan paket HTTP Payload tambahan hingga banner SSH-2.0- dimulai
            sehingga Dropbear/OpenSSH tidak pernah error 'Bad protocol version'
          - Real Client IP extraction via CF-Connecting-IP & X-Forwarded-For
"""

import asyncio
import json
import logging
import os
import signal
import socket
import sys
import time
from typing import Dict, Any

LISTEN_HOST = os.environ.get("SSH_WS_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("SSH_WS_PORT", "10015"))
DEFAULT_TARGET_HOST = "127.0.0.1"
DROPBEAR_PORT = int(os.environ.get("DROPBEAR_PORT", "109"))
OPENSSH_PORT = int(os.environ.get("OPENSSH_PORT", "22"))

LOG_DIR = "/var/log/jibsz"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "ssh_ws.log")
ACTIVE_CONN_FILE = os.path.join(LOG_DIR, "ssh_ws_active.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)

ACTIVE_CONNECTIONS: Dict[str, Dict[str, Any]] = {}
HTTP_METHODS = (b"GET ", b"POST ", b"CONNECT ", b"HEAD ", b"PUT ", b"OPTIONS ", b"PATCH ")


def persist_active_connections() -> None:
    try:
        tmp_path = f"{ACTIVE_CONN_FILE}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(list(ACTIVE_CONNECTIONS.values()), f, indent=2)
        os.replace(tmp_path, ACTIVE_CONN_FILE)
    except Exception as exc:
        logging.debug("Gagal menyimpan active connections: %s", exc)


def detect_backend_port() -> int:
    for port in (DROPBEAR_PORT, OPENSSH_PORT):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((DEFAULT_TARGET_HOST, port)) == 0:
                return port
    return OPENSSH_PORT


def extract_real_client_ip(headers_raw: str, peer_ip: str) -> str:
    headers: Dict[str, str] = {}
    for line in headers_raw.split("\r\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    cf_ip = headers.get("cf-connecting-ip")
    if cf_ip and cf_ip != "127.0.0.1":
        return cf_ip.split(",")[0].strip()

    xff = headers.get("x-forwarded-for")
    if xff:
        first_ip = xff.split(",")[0].strip()
        if first_ip and first_ip != "127.0.0.1":
            return first_ip

    x_real = headers.get("x-real-ip")
    if x_real and x_real != "127.0.0.1":
        return x_real.strip()

    return peer_ip


async def pipe_client_to_backend(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    conn_id: str,
    ssh_started: bool,
) -> None:
    """
    Relay trafik dari Client ke Dropbear/OpenSSH.
    Jika client menggunakan payload [split] (mengirim HTTP GET kedua sebelum SSH-2.0-),
    strip otomatis bagian HTTP tersebut hingga byte 'SSH-2.0-' ditemukan.
    """
    has_seen_ssh_banner = ssh_started
    try:
        while not reader.at_eof():
            chunk = await reader.read(16384)
            if not chunk:
                break

            if not has_seen_ssh_banner:
                if b"SSH-2.0-" in chunk:
                    idx = chunk.find(b"SSH-2.0-")
                    chunk = chunk[idx:]
                    has_seen_ssh_banner = True
                elif chunk.lstrip().startswith(HTTP_METHODS):
                    # Abaikan paket HTTP kedua dari payload [split]
                    continue
                else:
                    has_seen_ssh_banner = True

            writer.write(chunk)
            await writer.drain()
            if conn_id in ACTIVE_CONNECTIONS:
                ACTIVE_CONNECTIONS[conn_id]["up_bytes"] += len(chunk)
                ACTIVE_CONNECTIONS[conn_id]["last_seen"] = int(time.time())
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def pipe_backend_to_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    conn_id: str,
) -> None:
    try:
        while not reader.at_eof():
            chunk = await reader.read(16384)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
            if conn_id in ACTIVE_CONNECTIONS:
                ACTIVE_CONNECTIONS[conn_id]["down_bytes"] += len(chunk)
                ACTIVE_CONNECTIONS[conn_id]["last_seen"] = int(time.time())
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle_client(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    peername = client_writer.get_extra_info("peername")
    peer_ip = peername[0] if peername else "127.0.0.1"
    peer_port = peername[1] if peername else 0
    conn_id = f"{peer_ip}:{peer_port}:{int(time.time() * 1000)}"

    try:
        initial_data = await asyncio.wait_for(client_reader.read(8192), timeout=12.0)
    except Exception:
        client_writer.close()
        return

    if not initial_data:
        client_writer.close()
        return

    text_preview = initial_data.decode("utf-8", errors="ignore")
    real_ip = peer_ip
    leftover_payload = b""
    ssh_banner_already_seen = False

    if initial_data.lstrip().startswith(HTTP_METHODS):
        real_ip = extract_real_client_ip(text_preview, peer_ip)
        handshake_resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Server: Jibsz-Tunnel-WS/3.0 (@admj1btnl)\r\n"
            "\r\n"
        ).encode("utf-8")
        client_writer.write(handshake_resp)
        await client_writer.drain()

        if b"SSH-2.0-" in initial_data:
            idx = initial_data.find(b"SSH-2.0-")
            leftover_payload = initial_data[idx:]
            ssh_banner_already_seen = True
    else:
        leftover_payload = initial_data
        if b"SSH-2.0-" in initial_data:
            ssh_banner_already_seen = True

    target_port = detect_backend_port()
    try:
        backend_reader, backend_writer = await asyncio.wait_for(
            asyncio.open_connection(DEFAULT_TARGET_HOST, target_port),
            timeout=5.0,
        )
    except Exception as exc:
        logging.error("Gagal menghubungi backend SSH/Dropbear di %s:%d - %s", DEFAULT_TARGET_HOST, target_port, exc)
        client_writer.close()
        return

    ACTIVE_CONNECTIONS[conn_id] = {
        "conn_id": conn_id,
        "client_ip": real_ip,
        "backend_port": target_port,
        "connected_at": int(time.time()),
        "last_seen": int(time.time()),
        "up_bytes": 0,
        "down_bytes": 0,
    }
    persist_active_connections()
    logging.info("SSH-WS Connected | Client IP: %s -> Backend: 127.0.0.1:%d", real_ip, target_port)

    if leftover_payload:
        backend_writer.write(leftover_payload)
        await backend_writer.drain()

    try:
        await asyncio.gather(
            pipe_client_to_backend(client_reader, backend_writer, conn_id, ssh_banner_already_seen),
            pipe_backend_to_client(backend_reader, client_writer, conn_id),
        )
    finally:
        ACTIVE_CONNECTIONS.pop(conn_id, None)
        persist_active_connections()
        logging.info("SSH-WS Disconnected | Client IP: %s", real_ip)


async def periodic_sync() -> None:
    while True:
        await asyncio.sleep(5)
        persist_active_connections()


async def main() -> None:
    persist_active_connections()
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    logging.info("Jibsz SSH WebSocket Proxy V3 aktif di %s (Dropbear:%d / OpenSSH:%d)", addrs, DROPBEAR_PORT, OPENSSH_PORT)

    sync_task = asyncio.create_task(periodic_sync())
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    async with server:
        await stop_event.wait()
        sync_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
