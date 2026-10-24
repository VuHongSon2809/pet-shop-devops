"""Nạp dữ liệu mẫu (chỉ chạy khi bảng dịch vụ còn trống) để website có dữ liệu khi demo."""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from petshop.models import Appointment, Customer, Pet, SpaService

SERVICES = [
    ("Tắm & sấy cơ bản", "Tắm sữa tắm chuyên dụng, sấy khô, chải lông.", 150_000, 45),
    ("Cắt tỉa lông tạo kiểu", "Cắt tỉa theo giống, vệ sinh tai, cắt móng.", 300_000, 90),
    ("Combo Spa thư giãn", "Tắm thảo dược, massage, dưỡng lông, nước hoa.", 450_000, 120),
    ("Vệ sinh răng miệng", "Làm sạch mảng bám, khử mùi hôi miệng.", 120_000, 30),
    ("Cắt móng & vệ sinh tai", "Dịch vụ nhanh cho chó mèo mọi kích cỡ.", 80_000, 30),
    ("Trị ve rận", "Tắm thuốc đặc trị và kiểm tra da lông.", 250_000, 60),
]

CUSTOMERS = [
    ("Nguyễn Thị Lan", "0912345601", "lan.nguyen@example.com", "Phường Tân Thịnh, Thái Nguyên"),
    ("Trần Văn Minh", "0912345602", "minh.tran@example.com", "Phường Quang Trung, Thái Nguyên"),
    ("Lê Hoàng Anh", "0912345603", "anh.le@example.com", "Phường Đồng Quang, Thái Nguyên"),
    ("Phạm Thu Hà", "0912345604", "ha.pham@example.com", "Phường Hoàng Văn Thụ, Thái Nguyên"),
    ("Vũ Đức Thắng", "0912345605", "thang.vu@example.com", "Phường Gia Sàng, Thái Nguyên"),
]

PETS = [
    (0, "Mochi", "dog", "Poodle", "female", "4.20"),
    (0, "Bơ", "cat", "Anh lông ngắn", "male", "5.10"),
    (1, "Lucky", "dog", "Golden Retriever", "male", "28.50"),
    (2, "Miu", "cat", "Ba Tư", "female", "3.80"),
    (3, "Bông", "rabbit", "Thỏ Hà Lan", "female", "1.60"),
    (3, "Kem", "dog", "Corgi", "male", "11.20"),
    (4, "Đốm", "dog", "Dalmatian", "male", "22.00"),
]


class Command(BaseCommand):
    help = "Nạp dữ liệu mẫu cho cửa hàng thú cưng"

    @transaction.atomic
    def handle(self, *args, **options):
        if SpaService.objects.exists():
            self.stdout.write("Đã có dữ liệu, bỏ qua nạp dữ liệu mẫu.")
            return
        services = [SpaService.objects.create(name=n, description=d, price=p, duration_minutes=m)
                    for n, d, p, m in SERVICES]
        customers = [Customer.objects.create(full_name=n, phone=ph, email=e, address=a)
                     for n, ph, e, a in CUSTOMERS]
        pets = [Pet.objects.create(owner=customers[o], name=n, species=s, breed=b, gender=g,
                                   weight_kg=Decimal(w)) for o, n, s, b, g, w in PETS]

        base = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0)
        plan = [  # (ngày lệch, giờ, thú cưng, dịch vụ, trạng thái)
            (-6, 9, 0, 0, "done"), (-5, 10, 2, 1, "done"), (-4, 14, 3, 2, "done"),
            (-3, 9, 5, 0, "done"), (-2, 15, 6, 5, "cancelled"), (-1, 10, 1, 3, "done"), (0, 8, 4, 0, "done"),
            (0, 15, 1, 4, "confirmed"), (0, 17, 2, 3, "pending"),
            (1, 9, 0, 2, "confirmed"), (1, 13, 6, 0, "pending"), (2, 10, 4, 4, "pending"),
            (2, 14, 6, 1, "confirmed"), (3, 9, 3, 0, "pending"), (4, 16, 5, 2, "pending"),
        ]
        for day, hour, p, s, status in plan:
            Appointment.objects.create(pet=pets[p], service=services[s], status=status,
                                       start_at=base + timedelta(days=day, hours=hour - 9))
        self.stdout.write(self.style.SUCCESS(
            f"Đã nạp {len(services)} dịch vụ, {len(customers)} khách hàng, {len(pets)} thú cưng, {len(plan)} lịch hẹn."
        ))
