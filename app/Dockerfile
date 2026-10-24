# Image ứng dụng Django – chạy bằng user thường (non-root)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Tạo user/group riêng, không có shell đăng nhập, không có thư mục home
RUN groupadd --gid 10001 app \
 && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=root:root . .
# Gom file tĩnh lúc build để container có thể chạy với filesystem chỉ đọc
RUN DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput

USER 10001:10001
EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--worker-tmp-dir", "/dev/shm", \
     "--access-logfile", "-", \
     "--forwarded-allow-ips", "*"]
