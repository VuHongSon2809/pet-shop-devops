"""Tạo (hoặc giữ nguyên) tài khoản quản trị từ biến môi trường ADMIN_USERNAME/ADMIN_PASSWORD."""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Tạo superuser từ biến môi trường nếu chưa tồn tại"

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            raise CommandError("Thiếu biến môi trường ADMIN_PASSWORD")
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Tài khoản {username} đã tồn tại, bỏ qua.")
            return
        User.objects.create_superuser(username=username, email=os.environ.get("ADMIN_EMAIL", ""), password=password)
        self.stdout.write(self.style.SUCCESS(f"Đã tạo tài khoản quản trị {username}."))
