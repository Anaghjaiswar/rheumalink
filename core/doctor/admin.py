from django.contrib import admin
from .models import Doctor


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
	list_display = (
		"name",
		"specialization",
		"highest_qualification",
		"years_of_experience",
		"contact_no",
		"email",
	)
	list_filter = ("specialization", "highest_qualification", "years_of_experience")
	search_fields = ("name", "email", "contact_no", "specialization", "highest_qualification")
	ordering = ("name",)
