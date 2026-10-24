from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, Customer, Pet, SpaService


@override_settings(SPA_CAPACITY=1)
class AppointmentRuleTests(TestCase):
    def setUp(self):
        owner = Customer.objects.create(full_name="Test", phone="0900000001")
        self.pet = Pet.objects.create(owner=owner, name="A", weight_kg=Decimal("3"))
        self.pet2 = Pet.objects.create(owner=owner, name="B", weight_kg=Decimal("3"))
        self.svc = SpaService.objects.create(name="Tắm", price=100_000, duration_minutes=60)
        self.slot = (timezone.localtime() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)

    def make(self, pet, start):
        a = Appointment(pet=pet, service=self.svc, start_at=start)
        a.full_clean()
        a.save()
        return a

    def test_price_and_end_are_computed(self):
        a = self.make(self.pet, self.slot)
        self.assertEqual(a.price, 100_000)
        self.assertEqual(a.end_at - a.start_at, timedelta(minutes=60))

    def test_past_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make(self.pet, timezone.now() - timedelta(days=1))

    def test_outside_opening_hours_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make(self.pet, self.slot.replace(hour=19, minute=30))

    def test_capacity_and_overlap(self):
        self.make(self.pet, self.slot)
        with self.assertRaises(ValidationError):
            self.make(self.pet2, self.slot + timedelta(minutes=30))

    def test_cancelled_frees_slot(self):
        a = self.make(self.pet, self.slot)
        a.status = Appointment.Status.CANCELLED
        a.save()
        self.make(self.pet2, self.slot)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class PageTests(TestCase):
    def test_public_and_protected_pages(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
        get_user_model().objects.create_user("staff", password="x-very-long-pass")
        self.client.login(username="staff", password="x-very-long-pass")
        for name in ["dashboard", "customer_list", "pet_list", "service_list", "appointment_list",
                     "appointment_create"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
