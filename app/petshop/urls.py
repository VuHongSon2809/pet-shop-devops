from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("quan-ly/", views.dashboard, name="dashboard"),
    path("quan-ly/lich-hen/<int:pk>/trang-thai/<str:status>/", views.appointment_set_status,
         name="appointment_status"),
]

for slug, prefix, crud in [
    ("customer", "khach-hang", views.customer_views),
    ("pet", "thu-cung", views.pet_views),
    ("service", "dich-vu", views.service_views),
    ("appointment", "lich-hen", views.appointment_views),
]:
    urlpatterns += [
        path(f"quan-ly/{prefix}/", crud["list"], name=f"{slug}_list"),
        path(f"quan-ly/{prefix}/them/", crud["create"], name=f"{slug}_create"),
        path(f"quan-ly/{prefix}/<int:pk>/sua/", crud["update"], name=f"{slug}_update"),
        path(f"quan-ly/{prefix}/<int:pk>/xoa/", crud["delete"], name=f"{slug}_delete"),
    ]
