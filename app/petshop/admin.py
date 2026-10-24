from django.contrib import admin

from .models import Appointment, Customer, Pet, SpaService


class PetInline(admin.TabularInline):
    model = Pet
    extra = 0
    fields = ("name", "species", "breed", "weight_kg")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "pet_count", "created_at")
    search_fields = ("full_name", "phone", "email")
    inlines = [PetInline]

    @admin.display(description="Số thú cưng")
    def pet_count(self, obj):
        return obj.pets.count()


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("name", "species", "breed", "owner", "weight_kg")
    list_filter = ("species", "gender")
    search_fields = ("name", "breed", "owner__full_name", "owner__phone")
    autocomplete_fields = ("owner",)


@admin.register(SpaService)
class SpaServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "duration_minutes", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "pet", "customer_name", "service", "start_at", "status", "price")
    list_filter = ("status", "service", "start_at")
    search_fields = ("pet__name", "pet__owner__full_name", "pet__owner__phone")
    autocomplete_fields = ("pet",)
    date_hierarchy = "start_at"
    readonly_fields = ("end_at", "price", "created_at")

    @admin.display(description="Khách hàng")
    def customer_name(self, obj):
        return obj.pet.owner.full_name
