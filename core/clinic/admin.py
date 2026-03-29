from django.contrib import admin
from .models import Address, ClinicSettings


class ClinicSettingsInline(admin.StackedInline):
	model = ClinicSettings
	extra = 0


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
	list_display = ("line1", "city", "state", "country", "zip_code")
	list_filter = ("city", "state", "country")
	search_fields = ("line1", "line2", "city", "state", "country", "zip_code")
	inlines = [ClinicSettingsInline]


@admin.register(ClinicSettings)
class ClinicSettingsAdmin(admin.ModelAdmin):
	list_display = ("name", "contact_email", "contact_number", "address")
	search_fields = ("name", "contact_email", "contact_number", "address__city", "address__state")
	list_select_related = ("address",)
	autocomplete_fields = ("address",)


