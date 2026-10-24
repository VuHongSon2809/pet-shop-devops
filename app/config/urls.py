from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "PAWSPA · Quản trị cửa hàng thú cưng"
admin.site.site_title = "PAWSPA Admin"
admin.site.index_title = "Quản lý dữ liệu"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("dang-nhap/", auth_views.LoginView.as_view(), name="login"),
    path("dang-xuat/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("petshop.urls")),
]
