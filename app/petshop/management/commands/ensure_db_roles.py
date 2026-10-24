"""Tạo/cập nhật tài khoản PostgreSQL theo nguyên tắc quyền tối thiểu (least privilege).

Chạy bởi dịch vụ migrate bằng tài khoản chủ sở hữu (POSTGRES_USER):
  - petshop_app     : web dùng để chạy – chỉ SELECT/INSERT/UPDATE/DELETE, KHÔNG được tạo/xóa bảng
  - petshop_monitor : postgres-exporter dùng – chỉ có vai trò pg_monitor (đọc thống kê)
Lệnh chạy lại nhiều lần vẫn an toàn (idempotent) và cập nhật mật khẩu theo .env.
"""
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from psycopg import sql


class Command(BaseCommand):
    help = "Tạo tài khoản DB hạn chế quyền cho ứng dụng và exporter"

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write("Không phải PostgreSQL, bỏ qua.")
            return
        app_user, app_pw = os.environ.get("APP_DB_USER"), os.environ.get("APP_DB_PASSWORD")
        mon_user, mon_pw = os.environ.get("MONITOR_DB_USER"), os.environ.get("MONITOR_DB_PASSWORD")
        if not all([app_user, app_pw, mon_user, mon_pw]):
            raise CommandError("Thiếu APP_DB_USER/APP_DB_PASSWORD/MONITOR_DB_USER/MONITOR_DB_PASSWORD")

        db_name = connection.settings_dict["NAME"]
        owner = connection.settings_dict["USER"]
        connection.ensure_connection()
        raw = connection.connection  # kết nối psycopg gốc để ghép SQL an toàn
        I, L = sql.Identifier, sql.Literal

        statements = [
            # Tạo role nếu chưa có, luôn đặt lại mật khẩu theo .env
            sql.SQL("DO $$BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = {n}) "
                    "THEN CREATE ROLE {r} LOGIN; END IF; END$$").format(n=L(app_user), r=I(app_user)),
            sql.SQL("ALTER ROLE {r} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "CONNECTION LIMIT 20 PASSWORD {p}").format(r=I(app_user), p=L(app_pw)),
            sql.SQL("DO $$BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = {n}) "
                    "THEN CREATE ROLE {r} LOGIN; END IF; END$$").format(n=L(mon_user), r=I(mon_user)),
            sql.SQL("ALTER ROLE {r} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "CONNECTION LIMIT 3 PASSWORD {p}").format(r=I(mon_user), p=L(mon_pw)),
            sql.SQL("GRANT pg_monitor TO {r}").format(r=I(mon_user)),

            # Không ai khác ngoài các role được chỉ định kết nối/tạo đối tượng
            sql.SQL("REVOKE ALL ON DATABASE {d} FROM PUBLIC").format(d=I(db_name)),
            sql.SQL("GRANT CONNECT ON DATABASE {d} TO {a}, {m}").format(d=I(db_name), a=I(app_user), m=I(mon_user)),
            sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"),
            sql.SQL("GRANT USAGE ON SCHEMA public TO {a}").format(a=I(app_user)),

            # Quyền thao tác dữ liệu (DML) trên bảng hiện có và bảng tạo sau này
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {a}").format(a=I(app_user)),
            sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {a}").format(a=I(app_user)),
            sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {o} IN SCHEMA public "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {a}").format(o=I(owner), a=I(app_user)),
            sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {o} IN SCHEMA public "
                    "GRANT USAGE, SELECT ON SEQUENCES TO {a}").format(o=I(owner), a=I(app_user)),
        ]
        with connection.cursor() as cursor:
            for stmt in statements:
                cursor.execute(stmt.as_string(raw))
        self.stdout.write(self.style.SUCCESS(
            f"Đã cấu hình role {app_user} (chỉ DML) và {mon_user} (pg_monitor)."
        ))
