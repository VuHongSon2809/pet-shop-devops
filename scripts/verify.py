#!/usr/bin/env python3
"""Kiểm tra nhanh toàn bộ hệ thống sau khi `docker compose up -d`.

Chạy tại thư mục gốc dự án:  python3 scripts/verify.py
(Nếu user chưa thuộc nhóm docker thì chạy: sudo python3 scripts/verify.py)
Chỉ dùng thư viện chuẩn của Python 3.8+.
"""
import base64
import json
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = []
GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def check(group, name, ok, detail=""):
    RESULTS.append(ok)
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  [{mark}] {name}" + (f" – {detail}" if detail else ""))


def section(title):
    print(f"\n{YELLOW}== {title} =={RESET}")


def sh(*args, timeout=30):
    p = subprocess.run(list(args), cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def compose(*args, timeout=30):
    return sh("docker", "compose", *args, timeout=timeout)


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def http(url, auth=None, follow=True):
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE   # chứng chỉ tự ký
    handlers = [urllib.request.HTTPSHandler(context=ctx)]
    if not follow:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        handlers.append(NoRedirect)
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url)
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode())
    try:
        with opener.open(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, {}, str(e)


def container_info():
    code, out = compose("ps", "-a", "--format", "json")
    if code != 0:
        sys.exit(f"Không gọi được docker compose: {out}\nThử lại với: sudo python3 scripts/verify.py")
    out = out.strip()
    items = json.loads(out) if out.startswith("[") else [json.loads(l) for l in out.splitlines() if l.strip()]
    return {c["Service"]: c for c in items}


def inspect(container):
    code, out = sh("docker", "inspect", container)
    return json.loads(out)[0] if code == 0 else {}


def main():
    env = load_env()
    ip = env.get("SERVER_IP", "127.0.0.1")

    section("1. Container (docker compose ps)")
    services = container_info()
    expected = ["db", "migrate", "web", "nginx", "pgadmin", "prometheus", "grafana", "cadvisor",
                "nginx-exporter", "postgres-exporter", "loki", "promtail"]
    for s in expected:
        c = services.get(s)
        if not c:
            check("ps", s, False, "không tìm thấy")
        elif s == "migrate":
            check("ps", s, c.get("ExitCode") == 0 and c.get("State") == "exited", "Exited (0) = đã tạo bảng xong")
        else:
            health = c.get("Health") or "-"
            check("ps", s, c.get("State") == "running" and health in ("-", "", "healthy"),
                  f"{c.get('State')} / health={health}")

    section("2. Website + Nginx reverse proxy + HTTPS")
    code, headers, _ = http("http://127.0.0.1/", follow=False)
    check("web", "HTTP tự chuyển sang HTTPS", code == 301 and headers.get("Location", "").startswith("https://"),
          f"{code} → {headers.get('Location', '')}")
    code, headers, body = http("https://127.0.0.1/")
    check("web", "Trang chủ qua HTTPS", code == 200 and "PAWSPA" in body, f"HTTP {code}")
    for h in ["Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options",
              "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy"]:
        check("web", f"Header {h}", h in headers, headers.get(h, "thiếu")[:60])
    check("web", "Ẩn phiên bản Nginx (server_tokens off)", headers.get("Server", "") == "nginx", headers.get("Server", ""))
    code, _, body = http("https://127.0.0.1/healthz")
    check("web", "Django kết nối PostgreSQL (/healthz)", code == 200 and '"database": "ok"' in body, body[:60])
    code, _, _ = http("https://127.0.0.1/metrics")
    check("web", "/metrics không lộ ra ngoài qua Nginx", code == 404, f"HTTP {code}")

    section("3. Database + pgAdmin")
    code, out = compose("exec", "-T", "db", "psql", "-U", env["POSTGRES_USER"], "-d", env["POSTGRES_DB"], "-tAc",
                        "SELECT count(*) FROM petshop_appointment")
    check("db", "Có dữ liệu lịch hẹn trong PostgreSQL", code == 0 and out.strip().isdigit() and int(out) > 0,
          f"{out.strip()} lịch hẹn")
    code, _, _ = http("http://127.0.0.1:5050/misc/ping")
    check("db", "pgAdmin hoạt động (127.0.0.1:5050)", code == 200, f"HTTP {code}")

    section("4. Prometheus + Grafana")
    code, _, body = http("http://127.0.0.1:9090/api/v1/targets")
    try:
        targets = json.loads(body)["data"]["activeTargets"]
        down = [t["labels"]["job"] for t in targets if t["health"] != "up"]
        check("mon", "Prometheus targets UP", len(targets) >= 5 and not down,
              f"{len(targets) - len(down)}/{len(targets)} UP" + (f", DOWN: {down}" if down else ""))
    except (ValueError, KeyError):
        check("mon", "Prometheus targets UP", False, body[:80])
    for q in ["pg_up", "nginx_up"]:
        code, _, body = http(f"http://127.0.0.1:9090/api/v1/query?query={q}")
        try:
            val = json.loads(body)["data"]["result"][0]["value"][1]
        except (ValueError, KeyError, IndexError):
            val = "?"
        check("mon", f"{q} = 1", val == "1", f"giá trị {val}")
    code, _, body = http("http://127.0.0.1:3000/api/health")
    check("mon", "Grafana health", code == 200 and '"ok"' in body, body.replace("\n", " ")[:60])
    auth = (env.get("GRAFANA_ADMIN_USER", "admin"), env.get("GRAFANA_ADMIN_PASSWORD", ""))
    code, _, body = http("http://127.0.0.1:3000/api/dashboards/uid/petshop-overview", auth=auth)
    check("mon", "Dashboard PetShop đã provisioning", code == 200, f"HTTP {code}")

    section("5. Loki + Promtail")
    code, _, body = http("http://127.0.0.1:3000/api/datasources/proxy/uid/loki/loki/api/v1/label/job/values", auth=auth)
    jobs = json.loads(body).get("data", []) if code == 200 else []
    check("log", "Loki nhận log của nginx và web", {"nginx", "web"} <= set(jobs), f"job = {jobs}")

    section("6. Hardening")
    non_root = ["web", "nginx", "db", "pgadmin", "prometheus", "grafana", "loki", "nginx-exporter", "postgres-exporter"]
    for s in non_root:
        c = services.get(s)
        info = inspect(c["Name"]) if c else {}
        user = info.get("Config", {}).get("User", "")
        check("hard", f"{s} chạy non-root", user not in ("", "0", "root", "0:0"), f"user={user or 'root'}")
    for s in ["web", "nginx"]:
        info = inspect(services[s]["Name"]) if s in services else {}
        hc = info.get("HostConfig", {})
        check("hard", f"{s}: read-only + CapDrop ALL + no-new-privileges",
              hc.get("ReadonlyRootfs") and "ALL" in (hc.get("CapDrop") or [])
              and any("no-new-privileges" in o for o in hc.get("SecurityOpt") or []),
              f"ReadonlyRootfs={hc.get('ReadonlyRootfs')} CapDrop={hc.get('CapDrop')}")
    code, out = compose("exec", "-T", "web", "id")
    check("hard", "web: lệnh id trong container", "uid=10001" in out, out)
    with socket.socket() as sock:
        sock.settimeout(2)
        closed = sock.connect_ex(("127.0.0.1", 5432)) != 0
    check("hard", "PostgreSQL không mở cổng 5432 ra host", closed)
    code, out = compose("exec", "-T", "nginx", "wget", "-q", "-T", "3", "-O", "/dev/null", "http://db:5432")
    check("hard", "Nginx không nhìn thấy DB (tách mạng)", "bad address" in out or "resolve" in out.lower(), out[:60])
    code, out = compose("exec", "-T", "db", "psql", "-U", env.get("APP_DB_USER", "petshop_app"), "-d",
                        env["POSTGRES_DB"], "-c", "CREATE TABLE hack_test(id int)")
    check("hard", "User DB của web không được tạo bảng", code != 0 and "permission denied" in out, out.splitlines()[0] if out else "")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    code, tracked = sh("git", "ls-files", ".env")
    check("hard", ".env không bị commit", ".env" in gitignore and not tracked.strip())

    total, passed = len(RESULTS), sum(1 for r in RESULTS if r)
    color = GREEN if passed == total else RED
    print(f"\n{color}Kết quả: {passed}/{total} PASS{RESET}")
    print(f"Website: https://{ip}/   (Grafana/pgAdmin/Prometheus: qua SSH tunnel, xem README)")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
