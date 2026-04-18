from django.contrib import admin
from .models import Comorbidity, FileRecord, PatientDiagnosis, PatientMedicalInfo, PatientProfile, PatientQueries, PatientState


class FileRecordInline(admin.StackedInline):
	model = FileRecord
	extra = 0


class PatientMedicalInfoInline(admin.StackedInline):
	model = PatientMedicalInfo
	extra = 0
	filter_horizontal = ("comorbidities",)


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"first_name",
		"last_name",
		"sex",
		"type",
		"contact_no",
		"email",
		"date_registered",
	)
	list_filter = ("sex", "type", "date_registered")
	search_fields = ("first_name", "last_name", "contact_no", "email")
	readonly_fields = ("date_registered", "age_display")
	date_hierarchy = "date_registered"
	inlines = [FileRecordInline, PatientMedicalInfoInline]

	@admin.display(description="Age")
	def age_display(self, obj):
		return obj.get_age()


@admin.register(FileRecord)
class FileRecordAdmin(admin.ModelAdmin):
	list_display = ("patient", "internal_file_number", "external_file_number")
	search_fields = (
		"patient__first_name",
		"patient__last_name",
		"internal_file_number",
		"external_file_number",
	)
	list_select_related = ("patient",)


@admin.register(Comorbidity)
class ComorbidityAdmin(admin.ModelAdmin):
	list_display = ("name",)
	search_fields = ("name",)


@admin.register(PatientMedicalInfo)
class PatientMedicalInfoAdmin(admin.ModelAdmin):
	list_display = ("patient", "blood_group", "smokes", "alcohololic")
	list_filter = ("blood_group", "smokes", "alcohololic", "comorbidities")
	search_fields = ("patient__first_name", "patient__last_name", "known_allergies", "family_history")
	filter_horizontal = ("comorbidities",)
	list_select_related = ("patient",)


@admin.register(PatientDiagnosis)
class PatientDiagnosisAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"patient_link",
		"consultation_link",
		"disease_name",
		"state",
		"created_at",
	)
	list_filter = ("state", "created_at")
	search_fields = (
		"patient_link__first_name",
		"patient_link__last_name",
		"disease_name",
		"version_note",
	)
	readonly_fields = ("created_at",)
	date_hierarchy = "created_at"
	list_select_related = (
		"patient_link",
		"consultation_link",
		"joints_record",
		"rumat_diagnosis",
	)
	autocomplete_fields = ("patient_link", "consultation_link", "joints_record", "rumat_diagnosis")


@admin.register(PatientQueries)
class PatientQueriesAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"patient",
		"short_query",
		"is_resolved",
		"is_ai_response_approved",
		"created_at",
	)
	list_filter = ("is_resolved", "is_ai_response_approved", "created_at")
	search_fields = (
		"patient__first_name",
		"patient__last_name",
		"patient__contact_no",
		"query",
		"ai_generated_response",
	)
	readonly_fields = ("created_at",)
	date_hierarchy = "created_at"
	list_select_related = ("patient",)
	actions = ("mark_as_resolved", "approve_ai_response")

	@admin.display(description="Query")
	def short_query(self, obj):
		max_length = 70
		return obj.query if len(obj.query) <= max_length else f"{obj.query[:max_length]}..."

	@admin.action(description="Mark selected queries as resolved")
	def mark_as_resolved(self, request, queryset):
		queryset.update(is_resolved=True)

	@admin.action(description="Approve AI response for selected queries")
	def approve_ai_response(self, request, queryset):
		queryset.update(is_ai_response_approved=True)


@admin.register(PatientState)
class PatientStateAdmin(admin.ModelAdmin):
	list_display = ("patient", "state", "session_started_at", "created_at", "updated_at")
	list_filter = ("state", "created_at", "updated_at")
	search_fields = ("patient__first_name", "patient__last_name", "patient__contact_no")
	list_select_related = ("patient",)
	readonly_fields = ("created_at", "updated_at", "session_started_at")
