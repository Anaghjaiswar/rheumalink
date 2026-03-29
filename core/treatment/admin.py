from django.contrib import admin
from .models import (
	Appointment,
	Consultation,
	LabResult,
	Medicine,
	Prescription,
	PrescriptionItem,
	RumatDiagnosis,
	Vitals,
	jointspain,
)


class PrescriptionItemInline(admin.TabularInline):
	model = PrescriptionItem
	extra = 1
	autocomplete_fields = ("medicine",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"patient",
		"doctor",
		"appointment_date",
		"appointment_time",
		"token_number",
		"status",
	)
	list_filter = ("status", "appointment_date", "doctor")
	search_fields = (
		"patient__first_name",
		"patient__last_name",
		"doctor__name",
		"token_number",
		"reason_for_visit",
	)
	date_hierarchy = "appointment_date"
	list_select_related = ("patient", "doctor")
	autocomplete_fields = ("patient", "doctor")
	readonly_fields = ("created_at", "updated_at")


@admin.register(Vitals)
class VitalsAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"patient",
		"appointment",
		"weight",
		"height",
		"bp_systolic",
		"bp_diastolic",
		"pulse_rate",
		"spo2",
		"temperature",
	)
	list_filter = ("appointment__appointment_date",)
	search_fields = ("patient__first_name", "patient__last_name")
	list_select_related = ("patient", "appointment")
	autocomplete_fields = ("patient", "appointment")


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
	list_display = ("id", "report_name", "patient", "appointment", "is_verified", "created_at")
	list_filter = ("is_verified", "created_at")
	search_fields = (
		"report_name",
		"patient__first_name",
		"patient__last_name",
		"appointment__id",
	)
	list_select_related = ("patient", "appointment")
	autocomplete_fields = ("patient", "appointment")
	readonly_fields = ("created_at",)


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
	list_display = ("medicine_name", "generic_name", "form", "strength", "category")
	list_filter = ("form", "category")
	search_fields = ("medicine_name", "generic_name", "strength", "category")
	ordering = ("medicine_name",)


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
	list_display = ("id", "patient", "appointment", "created_at")
	list_filter = ("created_at",)
	search_fields = (
		"patient__first_name",
		"patient__last_name",
		"chief_complaints",
		"clinical_findings",
		"provisional_diagnosis",
	)
	list_select_related = ("patient", "appointment")
	autocomplete_fields = ("patient", "appointment")
	readonly_fields = ("created_at",)


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
	list_display = ("id", "consultation", "next_followup_date")
	list_filter = ("next_followup_date",)
	search_fields = (
		"consultation__patient__first_name",
		"consultation__patient__last_name",
		"lab_investigations",
		"advice_notes",
	)
	list_select_related = ("consultation", "consultation__patient")
	autocomplete_fields = ("consultation",)
	inlines = [PrescriptionItemInline]


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
	list_display = ("id", "prescription", "medicine", "dosage", "duration")
	list_filter = ("medicine",)
	search_fields = (
		"prescription__consultation__patient__first_name",
		"prescription__consultation__patient__last_name",
		"medicine__medicine_name",
		"dosage",
		"duration",
		"instructions",
	)
	list_select_related = ("prescription", "medicine")
	autocomplete_fields = ("prescription", "medicine")


@admin.register(jointspain)
class JointPainAdmin(admin.ModelAdmin):
	list_display = ("id", "patient_link", "date_of_assessment")
	list_filter = ("date_of_assessment",)
	search_fields = ("patient_link__first_name", "patient_link__last_name")
	list_select_related = ("patient_link",)
	autocomplete_fields = ("patient_link",)

	fieldsets = (
		("Assessment", {"fields": ("patient_link", "date_of_assessment")}),
		(
			"Upper Body Joints",
			{
				"fields": (
					"acromioclavicularright",
					"acromioclavicularleft",
					"sternoclavicularright",
					"sternoclavicularleft",
					"shoulderright",
					"shoulderleft",
					"elbowright",
					"elbowleft",
					"wristright",
					"wristleft",
				)
			},
		),
		(
			"Hand Joints",
			{
				"fields": (
					"mcp1right",
					"mcp1left",
					"mcp2right",
					"mcp2left",
					"mcp3right",
					"mcp3left",
					"mcp4right",
					"mcp4left",
					"mcp5right",
					"mcp5left",
					"pip1right",
					"pip1left",
					"pip2right",
					"pip2left",
					"pip3right",
					"pip3left",
					"pip4right",
					"pip4left",
					"pip5right",
					"pip5left",
				)
			},
		),
		(
			"Lower Body Joints",
			{
				"fields": (
					"kneeright",
					"kneeleft",
					"ankleright",
					"ankleleft",
					"mtp1right",
					"mtp1left",
					"mtp2right",
					"mtp2left",
					"mtp3right",
					"mtp3left",
					"mtp4right",
					"mtp4left",
					"mtp5right",
					"mtp5left",
				)
			},
		),
	)


@admin.register(RumatDiagnosis)
class RumatDiagnosisAdmin(admin.ModelAdmin):
	list_display = (
		"id",
		"patient_link",
		"msm",
		"ba",
		"der",
		"opth",
		"cons",
		"allergy",
		"sys",
		"ph",
	)
	list_filter = ("msm", "ba", "der", "opth", "cons", "allergy", "sys", "ph", "oh", "perh", "spe")
	search_fields = ("patient_link__first_name", "patient_link__last_name", "description_t")
	list_select_related = ("patient_link",)
	autocomplete_fields = ("patient_link",)

	fieldsets = (
		("Patient", {"fields": ("patient_link",)}),
		(
			"Musculoskeletal Manifestation",
			{
				"fields": (
					"msm",
					"duration_years_msm",
					"duration_months_msm",
					"duration_days_msm",
					"symmetricity",
					"pattern_addctive_msm",
					"relapsing_msm",
					"episodic_msm",
				)
			},
		),
		(
			"Back Ache",
			{
				"fields": (
					"ba",
					"duration_years_ba",
					"duration_months_ba",
					"duration_days_ba",
					"early_morning_stiffness_ba",
					"area_involved_low_ba",
					"area_involved_mid_ba",
					"area_involved_neck_ba",
					"area_involved_buttock_ba",
				)
			},
		),
		("Weakness", {"fields": ("wk", "description_wk")}),
		(
			"Dermatological",
			{
				"fields": (
					"der",
					"photosensitivity_der",
					"malarrash_der",
					"prupura_der",
					"rec_oral_ulcer_der",
					"gangrene_der",
					"raynauds_phenomenon_der",
					"skin_thickening_der",
					"dry_mouth_der",
					"psoriasis_skin_der",
					"psoriasis_scalp_der",
					"psoriasis_nail_der",
					"hair_loss_der",
					"urticaria_der",
				)
			},
		),
		(
			"Ophthalmological",
			{
				"fields": (
					"opth",
					"dry_eyes_opth",
					"scleritis_episcleritis_opth",
					"redness_opth",
					"iridocyclitis_opth",
					"bov_opth",
				)
			},
		),
		(
			"Constitutional",
			{
				"fields": (
					"cons",
					"wt_loss_cons",
					"wt_gain_cons",
					"fever_cons",
				)
			},
		),
		(
			"Allergy",
			{
				"fields": (
					"allergy",
					"description_drugs_allergy",
					"description_other_allergy",
				)
			},
		),
		(
			"Systems",
			{
				"fields": (
					"sys",
					"description_cardiorespiratory_sys",
					"description_gastrointestinal_sys",
					"description_cns_sys",
					"description_rs_sys",
				)
			},
		),
		(
			"Past History",
			{
				"fields": (
					"ph",
					"dm_ph",
					"htn_ph",
					"thyroid_ph",
					"ihd_ph",
					"seizures_ph",
					"stroke_ph",
					"leukoderma_ph",
				)
			},
		),
		("Obstetric History", {"fields": ("oh", "description_oh")}),
		(
			"Personal History",
			{
				"fields": (
					"perh",
					"appetite_normal_perh",
					"appetite_redused_perh",
					"sleep_normal_perh",
					"sleep_disturbed_perh",
					"smoking_perh",
					"drinking_perh",
					"tobacco_perh",
				)
			},
		),
		(
			"Spine Examination",
			{
				"fields": (
					"spe",
					"restricted_movement_spe",
					"description_spe",
				)
			},
		),
		("Overall Summary", {"fields": ("description_t",)}),
	)
