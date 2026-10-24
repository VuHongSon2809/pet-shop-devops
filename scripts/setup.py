#!/usr/bin/env python3
"""Chuẩn bị lần đầu: sinh file .env với mật khẩu ngẫu nhiên mạnh và chứng chỉ HTTPS tự ký.

Cách dùng (tại thư mục gốc dự án):
    python3 scripts/setup.py                 # tự nhận IP của máy
    python3 scripts/setup.py --ip 192.168.1.50

Script KHÔNG ghi đè .env đã có (tránh lệch mật khẩu với database đã khởi tạo).
"""
import argparse
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
CERT_DIR = ROOT / "nginx" / "certs"


def detect_ip():
    try:
        out = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout.split()
        if out:
            return out[0]
    except (OSError, subprocess.CalledProcessError):
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def strong_password(length=24):
    # token_urlsafe chỉ chứa A-Z a-z 0-9 - _ : an toàn cho .env và chuỗi kết nối
    return secrets.token_urlsafe(length)


def write_env(ip):
    if ENV_FILE.exists():
        print(f"[bỏ qua] {ENV_FILE.name} đã tồn tại – giữ nguyên mật khẩu hiện có.")
        return
    values = {
        "SERVER_IP": ip,
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(50),
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": strong_password(18),
        "POSTGRES_DB": "petshop",
        "POSTGRES_USER": "petshop_owner",
        "POSTGRES_PASSWORD": strong_password(),
        "APP_DB_USER": "petshop_app",
        "APP_DB_PASSWORD": strong_password(),
        "MONITOR_DB_USER": "petshop_monitor",
        "MONITOR_DB_PASSWORD": strong_password(),
        "PGADMIN_EMAIL": "admin@example.com",
        "PGADMIN_PASSWORD": strong_password(18),
        "GRAFANA_ADMIN_USER": "admin",
        "GRAFANA_ADMIN_PASSWORD": strong_password(18),
    }
    ENV_FILE.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    os.chmod(ENV_FILE, 0o600)  # chỉ chủ sở hữu được đọc
    print(f"[ok] Đã tạo {ENV_FILE.name} (quyền 600). Mật khẩu đăng nhập xem bằng: cat .env")


def write_cert(ip):
    crt, key = CERT_DIR / "server.crt", CERT_DIR / "server.key"
    if crt.exists() and key.exists():
        print("[bỏ qua] Chứng chỉ HTTPS đã tồn tại.")
        return
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    san = f"subjectAltName=DNS:localhost,IP:127.0.0.1,IP:{ip}"
    subprocess.run([
        "openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048", "-sha256", "-days", "365",
        "-keyout", str(key), "-out", str(crt),
        "-subj", "/C=VN/ST=Thai Nguyen/O=PAWSPA/CN=pawspa.local", "-addext", san,
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Nginx trong container chạy bằng uid 101 nên cần đọc được file khóa (bind mount chỉ đọc)
    os.chmod(crt, 0o644)
    os.chmod(key, 0o644)
    print(f"[ok] Đã tạo chứng chỉ tự ký cho localhost, 127.0.0.1, {ip} (hạn 365 ngày).")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ip", help="IP của máy chủ/VM (mặc định: tự nhận)")
    args = parser.parse_args()
    ip = args.ip or detect_ip()
    print(f"IP máy chủ: {ip}")
    write_env(ip)
    try:
        write_cert(ip)
    except FileNotFoundError:
        sys.exit("Thiếu openssl. Cài bằng: sudo apt install -y openssl")


if __name__ == "__main__":
    main()
