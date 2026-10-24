# PAWSPA – Hệ thống Quản lý Cửa hàng Thú cưng (Đề 28)

Website quản lý **thú cưng, dịch vụ spa, khách hàng và lịch hẹn**, triển khai toàn bộ bằng **Docker Compose**.

| Thành phần | Công nghệ |
|---|---|
| Ứng dụng web | Python 3.12 · Django 5.2 · Gunicorn |
| Cơ sở dữ liệu | PostgreSQL 16 + pgAdmin 4 |
| Reverse proxy | Nginx (HTTPS tự ký + security headers) |
| Giám sát | Prometheus + Grafana, cAdvisor, nginx-prometheus-exporter, postgres-exporter |
| Log tập trung | Loki + Promtail, truy vấn LogQL trong Grafana |
| Bảo mật | Non-root, cap_drop, read-only, tách 5 mạng, user DB hạn chế quyền, security headers |

```
Trình duyệt ──HTTPS──▶ Nginx ──HTTP──▶ Django (web) ──SQL──▶ PostgreSQL ◀── pgAdmin

Prometheus ◀── cAdvisor (container) · nginx-exporter (web server) · postgres-exporter (DB) · /metrics Django
Grafana ──▶ Prometheus

Docker (json-file log) ──▶ Promtail ──▶ Loki ◀── Grafana (LogQL)
```

## 1. Yêu cầu môi trường

- Ubuntu 22.04/24.04 (máy ảo VMware), RAM ≥ 4 GB, ổ trống ≥ 15 GB
- Docker Engine + Docker Compose plugin, Python 3, Git, OpenSSL

```bash
# Cài Docker Engine trên Ubuntu
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # đăng xuất/đăng nhập lại để dùng docker không cần sudo
```

## 2. Chạy lần đầu

```bash
git clone https://github.com/<MSSV>/pet-shop-devops.git
cd pet-shop-devops
python3 scripts/setup.py            # sinh .env (mật khẩu ngẫu nhiên) + chứng chỉ HTTPS tự ký
docker compose config --quiet       # kiểm tra cấu hình
docker compose up -d --build        # dựng image và chạy nền
docker compose ps -a                # migrate "Exited (0)" là đã tạo bảng xong
python3 scripts/verify.py           # kiểm tra tự động, mong đợi toàn bộ PASS
```

Mật khẩu đăng nhập nằm trong file `.env` (`cat .env`). File này **không** được commit.

## 3. Truy cập

| Dịch vụ | Địa chỉ | Tài khoản |
|---|---|---|
| Website | `https://<IP-VM>/` | `admin` / `ADMIN_PASSWORD` |
| Django Admin | `https://<IP-VM>/admin/` | như trên |
| pgAdmin | `http://127.0.0.1:15050` (qua SSH tunnel) | `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` |
| Grafana | `http://127.0.0.1:13000` (qua SSH tunnel) | `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` |
| Prometheus | `http://127.0.0.1:19090/targets` (qua SSH tunnel) | – |

Chứng chỉ tự ký nên trình duyệt sẽ cảnh báo: chọn **Advanced → Proceed**.

pgAdmin, Grafana và Prometheus chỉ mở trên `127.0.0.1` của VM (không lộ ra mạng). Từ Windows, mở PowerShell tạo tunnel rồi giữ nguyên cửa sổ:

```powershell
ssh -N -L 15050:127.0.0.1:5050 -L 13000:127.0.0.1:3000 -L 19090:127.0.0.1:9090 <user>@<IP-VM>
```

Trong pgAdmin, server **PetShop PostgreSQL** đã khai báo sẵn (host `db`, user `petshop_owner`, mật khẩu `POSTGRES_PASSWORD`).

## 4. Giám sát (Prometheus + Grafana)

- Prometheus → **Status → Targets**: 5 job `prometheus`, `containers`, `django`, `nginx`, `postgres` phải **UP**.
- Grafana tự nạp datasource và dashboard **PetShop · Giám sát hệ thống** (thư mục PetShop, cũng là trang chủ):
  CPU/RAM/mạng từng container, request & kết nối Nginx, mã HTTP & độ trễ Django,
  kết nối/giao dịch/dung lượng PostgreSQL và số lịch hẹn theo trạng thái (đọc từ DB).
- Endpoint `/metrics` của Django chỉ truy cập được trong mạng Docker; qua Nginx trả về 404.

## 5. Log tập trung (Loki + Promtail)

- Mọi container ghi log bằng driver `json-file` (xoay vòng 10 MB × 3) kèm nhãn tên service.
- Promtail đọc `/var/lib/docker/containers/*/*-json.log` (chỉ đọc), gắn nhãn `job=<tên service>` rồi đẩy vào Loki.
- Nginx ghi access log dạng JSON; web ghi log sự kiện dạng `event=... user=... ip=...` (logfmt).
- Grafana → **Explore** → chọn **Loki**. Các câu truy vấn mẫu: [docs/logql.md](docs/logql.md).

```logql
{job="nginx"}
{job="nginx"} | json | method="GET"
sum(count_over_time({job="nginx"}[5m]))
{job="nginx"} | json | status >= 400
{job="web"} | logfmt | event="login_failed"
```

## 6. Hardening (bảo mật hệ thống)

| Biện pháp | Áp dụng |
|---|---|
| Container non-root | web (uid 10001), nginx (uid 101), db (postgres), pgAdmin, Grafana, Prometheus, Loki, exporter (nobody) |
| Bỏ Linux capabilities | `cap_drop: ALL` + `no-new-privileges` cho hầu hết dịch vụ |
| Filesystem chỉ đọc | `read_only: true` cho web, migrate, nginx, Prometheus, Loki, Promtail, exporter (chỉ `/tmp` là tmpfs) |
| Tách mạng | 5 network: `frontend`, `admin`, `app`*, `data`*, `monitoring`* (*internal: không ra Internet, không publish cổng) |
| Giới hạn cổng | Chỉ Nginx mở 80/443; pgAdmin/Grafana/Prometheus chỉ `127.0.0.1`; PostgreSQL/Loki không mở cổng |
| Mật khẩu mạnh | `scripts/setup.py` sinh ngẫu nhiên (`secrets`), `.env` quyền 600 và nằm trong `.gitignore` |
| Hạn chế quyền DB | web dùng `petshop_app` (chỉ SELECT/INSERT/UPDATE/DELETE); exporter dùng `petshop_monitor` (pg_monitor); tài khoản chủ chỉ dùng cho migrate |
| Security headers + HTTPS | HSTS, CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy; TLS 1.2/1.3; ẩn phiên bản Nginx |
| Chống dò mật khẩu | Nginx `limit_req` 10 request/phút cho trang đăng nhập (trả 429); Django ghi log `event=login_failed` |
| Giới hạn tài nguyên | `mem_limit`, `cpus`, `pids_limit` cho từng container |

Ngoại lệ có chủ đích: **cAdvisor** cần `privileged` để đọc cgroup của host; **Promtail** chạy uid 0 để đọc file log Docker (thuộc root) nhưng đã bỏ toàn bộ capability, filesystem chỉ đọc và mount log ở chế độ chỉ đọc. Cả hai chỉ nằm trong mạng internal `monitoring`.

Kiểm tra tự động toàn bộ hệ thống (container, HTTPS, headers, DB, Prometheus, Grafana, Loki, hardening):

```bash
python3 scripts/verify.py        # hoặc: sudo python3 scripts/verify.py
docker compose exec web id       # uid=10001(app) – không phải root
docker compose exec db psql -U petshop_app -d petshop -c "CREATE TABLE x(id int)"   # permission denied
```

## 7. Lệnh thường dùng

```bash
docker compose logs -f web nginx     # xem log trực tiếp
docker compose logs --tail=50 promtail loki  # kiểm tra Promtail/Loki khi Explore không có log
docker compose restart nginx         # nạp lại cấu hình Nginx
docker compose down                  # dừng (giữ dữ liệu)
docker compose down -v               # dừng và XÓA dữ liệu – cẩn thận!
```

## 8. Cấu trúc thư mục

```
app/            Mã nguồn Django + Dockerfile
nginx/          Cấu hình reverse proxy, security headers, chứng chỉ (không commit)
pgadmin/        Khai báo sẵn server cho pgAdmin
prometheus/     Danh sách target cần thu thập metrics
grafana/        Provisioning datasource + dashboard JSON
loki/           Cấu hình Loki (lưu log 7 ngày)
promtail/       Cấu hình Promtail (đọc log Docker, gắn nhãn job)
docs/           Tài liệu truy vấn LogQL
scripts/        setup.py: sinh .env và chứng chỉ · verify.py: kiểm tra toàn hệ thống
compose.yaml    Định nghĩa toàn bộ dịch vụ
```

## 9. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `permission denied ... docker.sock` | Chạy lệnh với `sudo`, hoặc thêm user vào nhóm docker rồi đăng nhập lại |
| `migrate` Exited (1) | `docker compose logs migrate`; nếu đổi mật khẩu trong `.env` sau khi DB đã tạo thì phải dùng mật khẩu cũ hoặc `down -v` (mất dữ liệu) |
| Grafana "No data" | Kiểm tra Prometheus Targets, chọn **Last 15 minutes**, truy cập website để sinh traffic |
| Explore Loki không có log | `docker compose logs --tail=50 promtail loki`; kiểm tra khoảng thời gian và nhãn `{job="nginx"}` |
| Trình duyệt báo chứng chỉ không an toàn | Bình thường với chứng chỉ tự ký: Advanced → Proceed |
| Lỗi 429 ở trang đăng nhập | Đã vượt giới hạn 10 request/phút, đợi 1 phút |
