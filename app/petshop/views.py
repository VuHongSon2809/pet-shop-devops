import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Count, ProtectedError, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import AppointmentForm, CustomerForm, PetForm, SpaServiceForm
from .models import Appointment, Customer, Pet, SpaService

log = logging.getLogger("petshop")


def home(request):
    services = SpaService.objects.filter(is_active=True)
    return render(request, "petshop/home.html", {"services": services})


def healthz(request):
    """Dùng cho Docker healthcheck: kiểm tra ứng dụng và kết nối PostgreSQL."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok", "database": "ok"})
    except Exception:  # noqa: BLE001
        log.exception("event=healthcheck_failed")
        return JsonResponse({"status": "error", "database": "unreachable"}, status=503)


@login_required
def dashboard(request):
    now = timezone.localtime()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = Appointment.objects.select_related("pet__owner", "service").filter(
        start_at__gte=today_start, start_at__lt=today_start + timedelta(days=1)
    ).order_by("start_at")
    upcoming = Appointment.objects.select_related("pet__owner", "service").filter(
        start_at__gte=now, status__in=Appointment.ACTIVE_STATUSES
    ).order_by("start_at")[:8]
    month_revenue = Appointment.objects.filter(
        status=Appointment.Status.DONE, start_at__gte=today_start.replace(day=1)
    ).aggregate(total=Sum("price"))["total"] or 0
    by_status = dict(Appointment.objects.values_list("status").annotate(n=Count("id")))
    context = {
        "stats": [
            ("Khách hàng", Customer.objects.count(), "customer_list"),
            ("Thú cưng", Pet.objects.count(), "pet_list"),
            ("Dịch vụ đang mở", SpaService.objects.filter(is_active=True).count(), "service_list"),
            ("Lịch chờ xác nhận", by_status.get("pending", 0), "appointment_list"),
        ],
        "today": today,
        "upcoming": upcoming,
        "month_revenue": month_revenue,
    }
    return render(request, "petshop/dashboard.html", context)


# ---------- CRUD dùng chung cho 4 nhóm dữ liệu ----------

class CrudMixin(LoginRequiredMixin):
    title = ""
    slug = ""
    columns = []          # [(thuộc tính, nhãn)]
    search_fields = []

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title=self.title, slug=self.slug, columns=self.columns,
                   list_url=reverse(f"{self.slug}_list"), create_url=reverse(f"{self.slug}_create"))
        return ctx

    def get_success_url(self):
        return reverse(f"{self.slug}_list")


class CrudList(CrudMixin, ListView):
    template_name = "petshop/crud_list.html"
    paginate_by = 15

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            cond = Q()
            for f in self.search_fields:
                cond |= Q(**{f"{f}__icontains": q})
            qs = qs.filter(cond)
        status = self.request.GET.get("status")
        if status and hasattr(self.model, "Status"):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["rows"] = [
            (obj, [self.cell(obj, attr) for attr, _ in self.columns]) for obj in ctx["object_list"]
        ]
        if hasattr(self.model, "Status"):
            ctx["status_choices"] = self.model.Status.choices
            ctx["status"] = self.request.GET.get("status", "")
        return ctx

    @staticmethod
    def cell(obj, attr):
        display = getattr(obj, f"get_{attr}_display", None)
        if display:
            return display()
        value = obj
        for part in attr.split("."):
            value = getattr(value, part)
        if hasattr(value, "tzinfo") and value is not None:
            return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")
        if isinstance(value, bool):
            return "Có" if value else "Không"
        if isinstance(value, int) and attr in ("price",):
            return f"{value:,}đ".replace(",", ".")
        return value


class CrudForm(CrudMixin):
    template_name = "petshop/crud_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        action = "tạo" if isinstance(self, CreateView) else "cập nhật"
        event = "create" if isinstance(self, CreateView) else "update"
        log.info("event=%s_%s id=%s user=%s", self.slug, event, self.object.pk, self.request.user.username)
        messages.success(self.request, f"Đã {action} {self.title.lower()}: {self.object}")
        return response


class CrudDelete(CrudMixin, DeleteView):
    template_name = "petshop/crud_confirm_delete.html"

    def form_valid(self, form):
        obj = self.get_object()
        try:
            obj.delete()
        except ProtectedError:
            messages.error(self.request, f"Không thể xóa “{obj}” vì đang có dữ liệu liên quan.")
            return redirect(self.get_success_url())
        log.info("event=%s_delete id=%s user=%s", self.slug, obj.pk, self.request.user.username)
        messages.success(self.request, f"Đã xóa: {obj}")
        return redirect(self.get_success_url())


def build_crud(model, form_class, slug, title, columns, search_fields, queryset=None):
    attrs = dict(model=model, slug=slug, title=title, columns=columns, search_fields=search_fields)
    if queryset is not None:
        attrs["queryset"] = queryset
    return {
        "list": type(f"{model.__name__}List", (CrudList,), attrs).as_view(),
        "create": type(f"{model.__name__}Create", (CrudForm, CreateView), {**attrs, "form_class": form_class}).as_view(),
        "update": type(f"{model.__name__}Update", (CrudForm, UpdateView), {**attrs, "form_class": form_class}).as_view(),
        "delete": type(f"{model.__name__}Delete", (CrudDelete,), attrs).as_view(),
    }


customer_views = build_crud(
    Customer, CustomerForm, "customer", "Khách hàng",
    [("full_name", "Họ tên"), ("phone", "Điện thoại"), ("email", "Email"), ("address", "Địa chỉ")],
    ["full_name", "phone", "email"],
)
pet_views = build_crud(
    Pet, PetForm, "pet", "Thú cưng",
    [("name", "Tên"), ("species", "Loài"), ("breed", "Giống"), ("weight_kg", "Cân nặng (kg)"),
     ("owner.full_name", "Chủ nuôi")],
    ["name", "breed", "owner__full_name", "owner__phone"],
    queryset=Pet.objects.select_related("owner"),
)
service_views = build_crud(
    SpaService, SpaServiceForm, "service", "Dịch vụ spa",
    [("name", "Dịch vụ"), ("price", "Giá"), ("duration_minutes", "Phút"), ("is_active", "Đang mở")],
    ["name"],
)
appointment_views = build_crud(
    Appointment, AppointmentForm, "appointment", "Lịch hẹn",
    [("start_at", "Bắt đầu"), ("pet.name", "Thú cưng"), ("pet.owner.full_name", "Khách hàng"),
     ("service.name", "Dịch vụ"), ("price", "Thành tiền"), ("status", "Trạng thái")],
    ["pet__name", "pet__owner__full_name", "pet__owner__phone", "service__name"],
    queryset=Appointment.objects.select_related("pet__owner", "service"),
)


@login_required
@require_POST
def appointment_set_status(request, pk, status):
    appt = get_object_or_404(Appointment, pk=pk)
    allowed = {
        "pending": {"confirmed", "cancelled"},
        "confirmed": {"done", "cancelled"},
    }
    if status not in allowed.get(appt.status, set()):
        messages.error(request, "Không thể chuyển sang trạng thái này.")
    else:
        old = appt.status
        appt.status = status
        appt.save(update_fields=["status"])
        log.info("event=appointment_status id=%s from=%s to=%s user=%s", pk, old, status, request.user.username)
        messages.success(request, f"Lịch #{pk}: {appt.get_status_display()}")
    return redirect(request.POST.get("next") or reverse_lazy("appointment_list"))
