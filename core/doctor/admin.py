from django.contrib import admin
from .models import Doctor, Compounder


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
	list_display = (
		"get_full_name",
		"photo",
		"first_name",
		"last_name",
		"email",
		"specialization",
		"highest_qualification",
		"years_of_experience",
		"contact_no",
	)
	list_filter = ("specialization", "highest_qualification", "years_of_experience")
	search_fields = ("first_name", "last_name", "email", "contact_no", "specialization", "highest_qualification")
	ordering = ("email",)


@admin.register(Compounder)
class CompounderAdmin(admin.ModelAdmin):
	list_display = (
		"email",
		"first_name",
		"last_name",
		"contact_no",
		"qualification",
		"shift",
		"assigned_doctor",
		"is_head_compounder",
	)
	list_filter = ("shift", "is_head_compounder", "assigned_doctor")
	search_fields = ("email", "first_name", "last_name", "contact_no", "qualification")
	ordering = ("email",)
