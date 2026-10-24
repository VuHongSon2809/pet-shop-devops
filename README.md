# PAWSPA – Hệ thống Quản lý Cửa hàng Thú cưng (Đề 28)

Website quản lý **thú cưng, dịch vụ spa, khách hàng và lịch hẹn**, triển khai toàn bộ bằng **Docker Compose**.

| Thành phần | Công nghệ |
|---|---|
| Ứng dụng web | Python 3.12 · Django 5.2 · Gunicorn |
| Cơ sở dữ liệu | PostgreSQL 16 + pgAdmin 4 |
| Reverse proxy | Nginx (HTTPS tự ký + security headers) |

```
Trình duyệt ──HTTPS──▶ Nginx ──HTTP──▶ Django (web) ──SQL──▶ PostgreSQL ◀── pgAdmin
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
```

Mật khẩu đăng nhập nằm trong file `.env` (`cat .env`). File này **không** được commit.

## 3. Truy cập

| Dịch vụ | Địa chỉ | Tài khoản |
|---|---|---|
| Website | `https://<IP-VM>/` | `admin` / `ADMIN_PASSWORD` |
| Django Admin | `https://<IP-VM>/admin/` | như trên |
| pgAdmin | `http://127.0.0.1:5050` (qua SSH tunnel) | `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` |

Chứng chỉ tự ký nên trình duyệt sẽ cảnh báo: chọn **Advanced → Proceed**.

pgAdmin chỉ mở trên `127.0.0.1` của VM. Từ Windows, mở PowerShell tạo tunnel rồi giữ cửa sổ:

```powershell
ssh -N -L 15050:127.0.0.1:5050 <user>@<IP-VM>
```

Sau đó mở `http://127.0.0.1:15050`. Server **PetShop PostgreSQL** đã khai báo sẵn (host `db`, user `petshop_owner`, mật khẩu `POSTGRES_PASSWORD`).

## 4. Lệnh thường dùng

```bash
docker compose logs -f web nginx     # xem log
docker compose restart nginx         # nạp lại cấu hình Nginx
docker compose down                  # dừng (giữ dữ liệu)
docker compose down -v               # dừng và XÓA dữ liệu – cẩn thận!
```

## 5. Cấu trúc thư mục

```
app/            Mã nguồn Django + Dockerfile
nginx/          Cấu hình reverse proxy, security headers, chứng chỉ (không commit)
pgadmin/        Khai báo sẵn server cho pgAdmin
scripts/        setup.py: sinh .env và chứng chỉ
compose.yaml    Định nghĩa toàn bộ dịch vụ
```
