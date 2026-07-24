from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import Doctor, Compounder


@admin.register(Doctor)
class DoctorAdmin(BaseUserAdmin):
	list_display = (
		"get_full_name",
		"email",
		"specialization",
		"highest_qualification",
		"years_of_experience",
		"contact_no",
		"is_staff",
		"is_active",
	)
	list_filter = ("specialization", "highest_qualification", "years_of_experience", "is_staff", "is_active")
	search_fields = ("first_name", "last_name", "email", "contact_no", "specialization", "highest_qualification")
	ordering = ("email",)

	fieldsets = (
		(None, {"fields": ("email", "password")}),
		(_("Personal Info"), {"fields": ("first_name", "last_name", "photo", "contact_no")}),
		(_("Professional Details"), {"fields": ("specialization", "highest_qualification", "years_of_experience")}),
		(_("Permissions & Role"), {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
		(_("Important Dates"), {"fields": ("last_login", "date_joined")}),
	)
	add_fieldsets = (
		(
			None,
			{
				"classes": ("wide",),
				"fields": ("email", "password1", "password2", "first_name", "last_name", "specialization", "contact_no"),
			},
		),
	)

	def save_model(self, request, obj, form, change):
		if obj.password:
			try:
				from django.contrib.auth.hashers import identify_hasher
				identify_hasher(obj.password)
			except ValueError:
				obj.set_password(obj.password)
		super().save_model(request, obj, form, change)


@admin.register(Compounder)
class CompounderAdmin(BaseUserAdmin):
	list_display = (
		"email",
		"first_name",
		"last_name",
		"contact_no",
		"qualification",
		"shift",
		"assigned_doctor",
		"is_head_compounder",
		"is_active",
	)
	list_filter = ("shift", "is_head_compounder", "assigned_doctor", "is_active")
	search_fields = ("email", "first_name", "last_name", "contact_no", "qualification")
	ordering = ("email",)

	fieldsets = (
		(None, {"fields": ("email", "password")}),
		(_("Personal Info"), {"fields": ("first_name", "last_name", "contact_no")}),
		(_("Compounder Details"), {"fields": ("qualification", "shift", "assigned_doctor", "is_head_compounder")}),
		(_("Permissions & Role"), {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
		(_("Important Dates"), {"fields": ("last_login", "date_joined")}),
	)
	add_fieldsets = (
		(
			None,
			{
				"classes": ("wide",),
				"fields": ("email", "password1", "password2", "first_name", "last_name", "contact_no", "shift"),
			},
		),
	)

	def save_model(self, request, obj, form, change):
		if obj.password:
			try:
				from django.contrib.auth.hashers import identify_hasher
				identify_hasher(obj.password)
			except ValueError:
				obj.set_password(obj.password)
		super().save_model(request, obj, form, change)
