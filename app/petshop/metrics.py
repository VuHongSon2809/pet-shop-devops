"""Metrics nghiệp vụ cho Prometheus: số lịch hẹn theo trạng thái, số khách hàng, số thú cưng.

Giá trị được đọc trực tiếp từ PostgreSQL mỗi lần Prometheus scrape /metrics,
nên Grafana luôn hiển thị số liệu thật trong database.
"""
import logging

from django.db.models import Count
from prometheus_client.core import GaugeMetricFamily

log = logging.getLogger("petshop")


class PetshopCollector:
    def describe(self):
        # Trả về rỗng để prometheus_client không gọi collect() (truy vấn DB) lúc khởi động
        return []

    def collect(self):
        from .models import Appointment, Customer, Pet, SpaService

        try:
            counts = dict(Appointment.objects.values_list("status").annotate(n=Count("id")))
            appointments = GaugeMetricFamily(
                "petshop_appointments", "Số lịch hẹn theo trạng thái", labels=["status"]
            )
            for status, _label in Appointment.Status.choices:
                appointments.add_metric([status], counts.get(status, 0))
            yield appointments
            yield GaugeMetricFamily("petshop_customers", "Số khách hàng", value=Customer.objects.count())
            yield GaugeMetricFamily("petshop_pets", "Số thú cưng", value=Pet.objects.count())
            yield GaugeMetricFamily(
                "petshop_active_services", "Số dịch vụ spa đang cung cấp",
                value=SpaService.objects.filter(is_active=True).count(),
            )
        except Exception:  # noqa: BLE001 – không để lỗi DB làm hỏng endpoint /metrics
            log.exception("không đọc được metrics nghiệp vụ")
