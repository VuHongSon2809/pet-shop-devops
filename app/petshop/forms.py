from django import forms

from .models import Appointment, Customer, Pet, SpaService


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "check" if isinstance(field.widget, forms.CheckboxInput) else "input"
            field.widget.attrs.setdefault("class", css)


class CustomerForm(StyledModelForm):
    class Meta:
        model = Customer
        fields = ["full_name", "phone", "email", "address"]


class PetForm(StyledModelForm):
    class Meta:
        model = Pet
        fields = ["owner", "name", "species", "breed", "gender", "birth_date", "weight_kg", "notes"]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class SpaServiceForm(StyledModelForm):
    class Meta:
        model = SpaService
        fields = ["name", "description", "price", "duration_minutes", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class AppointmentForm(StyledModelForm):
    class Meta:
        model = Appointment
        fields = ["pet", "service", "start_at", "status", "note"]
        widgets = {"start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pet"].queryset = Pet.objects.select_related("owner")
        if not self.instance.pk:
            self.fields["service"].queryset = SpaService.objects.filter(is_active=True)
