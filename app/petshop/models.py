from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

phone_validator = RegexValidator(r"^0\d{9,10}$", "Số điện thoại gồm 10–11 chữ số, bắt đầu bằng 0.")


class Customer(models.Model):
    full_name = models.CharField("Họ tên", max_length=120)
    phone = models.CharField("Điện thoại", max_length=11, unique=True, validators=[phone_validator])
    email = models.EmailField("Email", blank=True)
    address = models.CharField("Địa chỉ", max_length=255, blank=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Khách hàng"
        verbose_name_plural = "Khách hàng"
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class Pet(models.Model):
    class Species(models.TextChoices):
        DOG = "dog", "Chó"
        CAT = "cat", "Mèo"
        BIRD = "bird", "Chim"
        RABBIT = "rabbit", "Thỏ"
        OTHER = "other", "Khác"

    class Gender(models.TextChoices):
        MALE = "male", "Đực"
        FEMALE = "female", "Cái"

    owner = models.ForeignKey(Customer, verbose_name="Chủ nuôi", on_delete=models.PROTECT, related_name="pets")
    name = models.CharField("Tên", max_length=60)
    species = models.CharField("Loài", max_length=10, choices=Species.choices, default=Species.DOG)
    breed = models.CharField("Giống", max_length=80, blank=True)
    gender = models.CharField("Giới tính", max_length=6, choices=Gender.choices, default=Gender.MALE)
    birth_date = models.DateField("Ngày sinh", null=True, blank=True)
    weight_kg = models.DecimalField(
        "Cân nặng (kg)", max_digits=5, decimal_places=2, validators=[MinValueValidator(0.1)]
    )
    notes = models.TextField("Ghi chú sức khỏe", blank=True)

    class Meta:
        verbose_name = "Thú cưng"
        verbose_name_plural = "Thú cưng"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} – {self.get_species_display()} ({self.owner.full_name})"


class SpaService(models.Model):
    name = models.CharField("Tên dịch vụ", max_length=100, unique=True)
    description = models.TextField("Mô tả", blank=True)
    price = models.PositiveIntegerField("Giá (VNĐ)")
    duration_minutes = models.PositiveIntegerField("Thời lượng (phút)", validators=[MinValueValidator(15)])
    is_active = models.BooleanField("Đang cung cấp", default=True)

    class Meta:
        verbose_name = "Dịch vụ spa"
        verbose_name_plural = "Dịch vụ spa"
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} – {self.price:,}đ".replace(",", ".")


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Chờ xác nhận"
        CONFIRMED = "confirmed", "Đã xác nhận"
        DONE = "done", "Hoàn thành"
        CANCELLED = "cancelled", "Đã hủy"

    ACTIVE_STATUSES = (Status.PENDING, Status.CONFIRMED)

    pet = models.ForeignKey(Pet, verbose_name="Thú cưng", on_delete=models.PROTECT, related_name="appointments")
    service = models.ForeignKey(
        SpaService, verbose_name="Dịch vụ", on_delete=models.PROTECT, related_name="appointments"
    )
    start_at = models.DateTimeField("Bắt đầu")
    end_at = models.DateTimeField("Kết thúc", editable=False)
    status = models.CharField("Trạng thái", max_length=10, choices=Status.choices, default=Status.PENDING)
    price = models.PositiveIntegerField("Thành tiền (VNĐ)", editable=False)
    note = models.CharField("Ghi chú", max_length=255, blank=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        verbose_name = "Lịch hẹn"
        verbose_name_plural = "Lịch hẹn"
        ordering = ["-start_at"]
        indexes = [models.Index(fields=["start_at", "end_at", "status"])]

    def __str__(self):
        local = timezone.localtime(self.start_at)
        return f"#{self.pk} {self.pet.name} – {self.service.name} lúc {local:%d/%m/%Y %H:%M}"

    @property
    def customer(self):
        return self.pet.owner

    def _compute_end(self):
        return self.start_at + timedelta(minutes=self.service.duration_minutes)

    def clean(self):
        """Quy tắc nghiệp vụ: giờ mở cửa, không đặt lịch quá khứ, không trùng lịch, giới hạn số chỗ."""
        if not (self.start_at and self.service_id and self.pet_id):
            return
        errors = {}
        end_at = self._compute_end()
        local_start, local_end = timezone.localtime(self.start_at), timezone.localtime(end_at)

        if self.status in self.ACTIVE_STATUSES:
            if self._state.adding and self.start_at < timezone.now():
                errors["start_at"] = "Không thể đặt lịch ở thời điểm đã qua."
            elif local_start.hour < settings.SPA_OPEN_HOUR or local_end.date() != local_start.date() or (
                local_end.hour, local_end.minute) > (settings.SPA_CLOSE_HOUR, 0):
                errors["start_at"] = (
                    f"Cửa hàng phục vụ từ {settings.SPA_OPEN_HOUR}:00 đến {settings.SPA_CLOSE_HOUR}:00; "
                    f"dịch vụ này kết thúc lúc {local_end:%H:%M}."
                )
            if not self.service.is_active and self._state.adding:
                errors["service"] = "Dịch vụ này đã ngừng cung cấp."

            overlapping = Appointment.objects.filter(
                status__in=self.ACTIVE_STATUSES, start_at__lt=end_at, end_at__gt=self.start_at
            ).exclude(pk=self.pk)
            if overlapping.filter(pet_id=self.pet_id).exists():
                errors["pet"] = "Thú cưng này đã có lịch hẹn khác trùng khung giờ."
            elif overlapping.count() >= settings.SPA_CAPACITY:
                errors["start_at"] = (
                    f"Khung giờ này đã đủ {settings.SPA_CAPACITY} lịch, vui lòng chọn giờ khác."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.end_at = self._compute_end()
        if not self.price:
            self.price = self.service.price  # chốt giá tại thời điểm đặt
        super().save(*args, **kwargs)
