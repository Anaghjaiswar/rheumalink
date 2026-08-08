from datetime import date
import json
from io import BytesIO


from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
import requests

from user.models import User
from doctor.models import Doctor
from patient.models import Comorbidity, FileRecord, PatientMedicalInfo, PatientProfile
from patient.models import PatientDiagnosis
from .forms import (
	AppointmentForm,
	AppointmentUpdateForm,
	ConsultationForm,
	DoctorFilterForm,
	JointPainForm,
	LabResultForm,
	PatientDiagnosisForm,
	PatientMedicalInfoForm,
	PatientProfileForm,
	PrescriptionForm,
	VitalsForm,
	RumatDiagnosisForm,
)
from .models import Appointment, Consultation, LabResult, Medicine, Prescription, PrescriptionItem, RumatDiagnosis, Vitals, jointspain, LabTest
from .services import RheumaAnalyticsService
from .tasks import process_lab_report_task
from logging import getLogger

all_logs = getLogger("all_logs.log")


def _queue_group(doctor_id=None):
	return f"doctor_queue_{doctor_id or 'all'}"


def _broadcast_queue_update(doctor_id=None):
	channel_layer = get_channel_layer()
	if not channel_layer:
		return

	targets = {_queue_group(), _queue_group(doctor_id)} if doctor_id else {_queue_group()}
	for group in targets:
		async_to_sync(channel_layer.group_send)(
			group,
			{
				"type": "queue.update",
				"message": "Queue changed",
			},
		)


def _generate_prescription_pdf(prescription):
	"""Generates prescription PDF using the central Gotenberg HTML-to-PDF engine with query & caching optimizations."""
	from django.template.loader import render_to_string
	from django.core.cache import cache
	from clinic.models import ClinicSettings
	from services.ai_service_manager import AIServiceManager
	from .models import Prescription

	# Optimization 1: Cache ClinicSettings lookup to avoid hitting DB on every PDF render
	clinic = cache.get("clinic_settings_cached")
	if clinic is None:
		clinic = ClinicSettings.objects.select_related("address").first()
		if clinic:
			cache.set("clinic_settings_cached", clinic, 300)

	# Optimization 2: Pre-fetch all necessary relational objects in 1 optimized SQL query if not loaded
	if not (hasattr(prescription, '_state') and getattr(prescription._state, 'fields_cache', None) and 'consultation' in prescription._state.fields_cache):
		prescription = (
			Prescription.objects.select_related(
				"consultation__patient__filerecord",
				"consultation__appointment__doctor",
			)
			.prefetch_related(
				"items__medicine",
				"prescribed_tests",
			)
			.get(id=prescription.id)
		)

	consultation = prescription.consultation
	patient = consultation.patient if consultation else None
	doctor = consultation.appointment.doctor if (consultation and consultation.appointment) else None
	prescription_items = prescription.items.select_related("medicine").all()
	prescribed_tests = prescription.prescribed_tests.all()
	
	file_number = '-'
	if patient and hasattr(patient, 'filerecord'):
		try:
			file_number = patient.filerecord.internal_file_number
		except Exception:
			file_number = '-'
	
	context = {
		"clinic": clinic,
		"doctor": doctor,
		"patient": patient,
		"consultation": consultation,
		"prescription": prescription,
		"prescription_items": prescription_items,
		"prescribed_tests": prescribed_tests,
		"file_number": file_number,
	}
	
	html_content = render_to_string("treatment/prescription_pdf.html", context)
	return AIServiceManager.render_pdf(html_content, clinic)


def _doctor_queryset(doctor_id):
	base = Appointment.objects.select_related("patient__filerecord", "doctor").filter(appointment_date=date.today())
	if doctor_id:
		base = base.filter(doctor_id=doctor_id)
	return base


@login_required(login_url='login')
def compounder_dashboard(request):
	user_role = getattr(request.user, 'role', None)
	is_compounder = getattr(request.user, 'is_compounder', False) or user_role == User.Role.COMPOUNDER
	is_doctor = getattr(request.user, 'is_doctor', False) or user_role == User.Role.DOCTOR
	if not (is_compounder or is_doctor or request.user.is_staff or request.user.is_superuser):
		messages.error(request, "Access restricted. Please log in with a Compounder or Doctor account.")
		return redirect(f"/login/?next={request.path}")

	patient_form_bound = None
	appointment_form_bound = None
	vitals_form_bound = None
	medical_form_bound = None
	report_form_bound = None

	def _redirect_cmp(patient_id=None):
		pid = patient_id or request.POST.get("patient_id") or request.POST.get("patient")
		query = f"?selected_patient={pid}" if pid else ""
		return redirect(f"/compounder-dashboard/{query}")

	if request.method == "POST":

		action = request.POST.get("action")

		if action == "register_patient":
			patient_form = PatientProfileForm(request.POST)
			if patient_form.is_valid():
				patient = patient_form.save()
				ext_num = request.POST.get("external_file_number", "").strip() or None
				file_rec, created = FileRecord.objects.get_or_create(patient=patient, defaults={"external_file_number": ext_num})
				if not created and ext_num and not file_rec.external_file_number:
					file_rec.external_file_number = ext_num
					file_rec.save()
				messages.success(request, f"Patient '{patient.get_full_name()}' registered successfully. File Record: {file_rec.internal_file_number}")
				return _redirect_cmp(patient.id)
			else:
				patient_form_bound = patient_form
				err_list = [f"{k.replace('_', ' ').title()}: {v[0]}" for k, v in patient_form.errors.items()]
				messages.error(request, f"Could not create patient profile. Errors: {'; '.join(err_list)}")

		elif action == "create_appointment":
			appointment_form = AppointmentForm(request.POST)
			if appointment_form.is_valid():
				appointment = appointment_form.save()
				messages.success(request, f"Appointment created with token {appointment.token_number}.")
				_broadcast_queue_update(appointment.doctor_id)
				return _redirect_cmp(appointment.patient_id)
			else:
				appointment_form_bound = appointment_form
				err_list = [f"{k.replace('_', ' ').title()}: {v[0]}" for k, v in appointment_form.errors.items()]
				messages.error(request, f"Appointment creation failed: {'; '.join(err_list)}")

		elif action == "capture_vitals":
			appointment = get_object_or_404(Appointment, id=request.POST.get("appointment_id"))
			instance = Vitals.objects.filter(appointment=appointment).first()
			vitals_form = VitalsForm(request.POST, instance=instance)
			if vitals_form.is_valid():
				vitals = vitals_form.save(commit=False)
				vitals.appointment = appointment
				vitals.patient = appointment.patient
				vitals.save()
				messages.success(request, "Vitals saved.")
				return _redirect_cmp(appointment.patient_id)
			else:
				vitals_form_bound = vitals_form
				messages.error(request, "Invalid vitals data.")

		elif action == "update_appointment":
			appointment = get_object_or_404(Appointment, id=request.POST.get("appointment_id"))
			update_form = AppointmentUpdateForm(request.POST, instance=appointment)
			if update_form.is_valid():
				updated = update_form.save()
				messages.success(request, "Appointment updated.")
				_broadcast_queue_update(updated.doctor_id)
				return _redirect_cmp(updated.patient_id)
			else:
				messages.error(request, "Could not update appointment.")

		elif action == "save_medical_info":
			patient = get_object_or_404(PatientProfile, id=request.POST.get("patient_id"))
			existing = PatientMedicalInfo.objects.filter(patient=patient).first()
			medical_form = PatientMedicalInfoForm(request.POST, instance=existing)
			if medical_form.is_valid():
				medical_info = medical_form.save(commit=False)
				medical_info.patient = patient
				medical_info.save()
				medical_form.save_m2m()
				custom = medical_form.cleaned_data.get("custom_comorbidity")
				if custom:
					comorbidity, _ = Comorbidity.objects.get_or_create(name=custom.strip())
					medical_info.comorbidities.add(comorbidity)
				messages.success(request, "Patient medical info saved.")
				return _redirect_cmp(patient.id)
			else:
				medical_form_bound = medical_form
				messages.error(request, "Medical info is invalid.")

		elif action == "upload_lab_report":
			report_form = LabResultForm(request.POST, request.FILES)
			if report_form.is_valid():
				report = report_form.save()
				messages.success(request, "Lab report uploaded.")
				return _redirect_cmp(report.patient_id)
			else:
				report_form_bound = report_form
				messages.error(request, "Lab report upload failed.")

		elif action == "sync_lab_report":
			report = get_object_or_404(LabResult, id=request.POST.get("report_id"))
			process_lab_report_task.delay(report.id)
			messages.success(request, "Lab report sync triggered on primary worker.")
			return _redirect_cmp(report.patient_id)

	search_q = request.GET.get("search_q", "").strip()
	is_recent_list = False
	if search_q:
		from django.db.models import Q
		search_results = PatientProfile.objects.select_related("filerecord").filter(
			Q(first_name__icontains=search_q) |
			Q(last_name__icontains=search_q) |
			Q(contact_no__icontains=search_q) |
			Q(filerecord__internal_file_number__icontains=search_q) |
			Q(filerecord__external_file_number__icontains=search_q)
		).distinct()
	else:
		search_results = PatientProfile.objects.select_related("filerecord").order_by("-id")[:5]
		is_recent_list = True

	today_appointments = Appointment.objects.select_related("patient__filerecord", "doctor").filter(
		appointment_date=date.today()
	)

	context = {
		"patient_form": patient_form_bound or PatientProfileForm(),
		"appointment_form": appointment_form_bound or AppointmentForm(initial={"status": "T"}),
		"vitals_form": vitals_form_bound or VitalsForm(),
		"medical_form": medical_form_bound or PatientMedicalInfoForm(),
		"report_form": report_form_bound or LabResultForm(),
		"today_appointments": today_appointments,
		"recent_patients": PatientProfile.objects.select_related("filerecord").order_by("-id")[:10],
		"pending_reports": LabResult.objects.filter(is_verified=False).select_related("patient__filerecord", "appointment")[:10],
		"search_results": search_results,
		"is_recent_list": is_recent_list,
	}
	return render(request, "treatment/compounder_dashboard.html", context)


@login_required(login_url='login')
def doctor_dashboard(request):
	user_role = getattr(request.user, 'role', None)
	is_doctor = getattr(request.user, 'is_doctor', False) or user_role == User.Role.DOCTOR
	if not (is_doctor or request.user.is_staff or request.user.is_superuser):
		messages.error(request, "Access restricted to doctors. Please log in with a Doctor account.")
		return redirect(f"/login/?next={request.path}")

	doctor_id = request.GET.get("doctor") or request.POST.get("doctor_id")
	if not doctor_id and is_doctor:
		doc_obj = Doctor.objects.filter(id=request.user.id).first()
		if doc_obj:
			doctor_id = doc_obj.id

	selected_doctor = None

	if doctor_id:
		try:
			doctor_id = int(doctor_id)
		except (TypeError, ValueError):
			doctor_id = None

	if request.method == "POST":
		action = request.POST.get("action")
		active_appt_id = request.POST.get("active_appt_id") or request.POST.get("appointment_id")
		download_rx_id = None

		if action == "update_status":
			appointment = get_object_or_404(Appointment, id=request.POST.get("appointment_id"))
			update_form = AppointmentUpdateForm(request.POST, instance=appointment)
			if update_form.is_valid():
				appt = update_form.save()
				messages.success(request, "Appointment status updated.")
				_broadcast_queue_update(appt.doctor_id)
			else:
				messages.error(request, "Could not update appointment status.")

		elif action == "capture_vitals":
			appointment = get_object_or_404(Appointment, id=request.POST.get("appointment_id"))
			instance = Vitals.objects.filter(appointment=appointment).first()
			vitals_form = VitalsForm(request.POST, instance=instance)
			if vitals_form.is_valid():
				vitals = vitals_form.save(commit=False)
				vitals.appointment = appointment
				vitals.patient = appointment.patient
				vitals.save()
				messages.success(request, "Vitals saved successfully.")
			else:
				messages.error(request, "Invalid vitals data.")

		elif action == "save_consultation":
			appointment = get_object_or_404(Appointment, id=request.POST.get("appointment_id"))
			consultation, _ = Consultation.objects.get_or_create(
				appointment=appointment,
				defaults={"patient": appointment.patient},
			)

			consult_form = ConsultationForm(request.POST, instance=consultation)
			prescription, _ = Prescription.objects.get_or_create(consultation=consultation)
			prescription_form = PrescriptionForm(request.POST, instance=prescription)

			if consult_form.is_valid() and prescription_form.is_valid():
				consultation = consult_form.save(commit=False)
				consultation.patient = appointment.patient
				consultation.appointment = appointment
				consultation.save()

				prescription = prescription_form.save(commit=False)
				prescription.consultation = consultation
				prescription.save()
				
				# Save many-to-many relationship of prescribed tests
				test_ids = request.POST.getlist("prescribed_tests")
				prescription.prescribed_tests.set(test_ids)

				medicine_ids = request.POST.getlist("medicine")
				dosages = request.POST.getlist("dosage")
				durations = request.POST.getlist("duration")
				instructions = request.POST.getlist("instructions")

				prescription.items.all().delete()
				for idx, medicine_id in enumerate(medicine_ids):
					if not medicine_id:
						continue
					try:
						medicine = Medicine.objects.get(id=int(medicine_id))
					except (Medicine.DoesNotExist, ValueError, TypeError):
						continue

					PrescriptionItem.objects.create(
						prescription=prescription,
						medicine=medicine,
						dosage=dosages[idx] if idx < len(dosages) else "",
						duration=durations[idx] if idx < len(durations) else "",
						instructions=instructions[idx] if idx < len(instructions) else "",
					)

				# Offload PDF generation to Celery background task
				from .tasks import generate_prescription_pdf_task
				try:
					generate_prescription_pdf_task.delay(prescription.id)
				except Exception:
					# Fallback synchronously if Celery broker is unavailable
					pdf_bytes = _generate_prescription_pdf(prescription)
					prescription.prescription_pdf.save(
						f"rx_{consultation.id}.pdf",
						ContentFile(pdf_bytes),
						save=True,
					)

				appointment.status = request.POST.get("post_consult_status") or appointment.status
				appointment.save(update_fields=["status", "updated_at"])
				_broadcast_queue_update(appointment.doctor_id)
				messages.success(request, "Consultation and prescription saved.")
				download_rx_id = prescription.id
			else:
				messages.error(request, "Consultation form contains invalid data.")

		elif action == "save_diagnosis":
			appointment = get_object_or_404(Appointment, id=request.POST.get("appointment_id"))
			consultation = Consultation.objects.filter(appointment=appointment).first()
			if not consultation:
				consultation = Consultation.objects.create(patient=appointment.patient, appointment=appointment)

			# Fetch existing diagnosis for this consultation to avoid duplicates
			existing_diag = PatientDiagnosis.objects.filter(consultation_link=consultation).first()
			diagnosis_form = PatientDiagnosisForm(request.POST, instance=existing_diag)

			if diagnosis_form.is_valid():
				joint_record = (
					jointspain.objects.filter(patient_link=appointment.patient)
					.order_by("-date_of_assessment")
					.first()
				)

				# Fetch latest symptoms checklist if any exists
				rumat_diagnosis = (
					RumatDiagnosis.objects.filter(patient_link=appointment.patient)
					.order_by("-id")
					.first()
				)

				diagnosis = diagnosis_form.save(commit=False)
				diagnosis.patient_link = appointment.patient
				diagnosis.consultation_link = consultation
				diagnosis.joints_record = joint_record
				diagnosis.rumat_diagnosis = rumat_diagnosis
				diagnosis.save()
				if joint_record:
					messages.success(request, "Patient diagnosis page saved with latest joint chart.")
				else:
					messages.warning(request, "Diagnosis saved, but no joint chart exists yet. Create one from Joint Chart page.")
			else:
				messages.error(request, "Diagnosis data is invalid.")

		elif action == "save_medical_info_doctor":
			patient = get_object_or_404(PatientProfile, id=request.POST.get("patient_id"))
			existing = PatientMedicalInfo.objects.filter(patient=patient).first()
			medical_form = PatientMedicalInfoForm(request.POST, instance=existing)
			if medical_form.is_valid():
				medical_info = medical_form.save(commit=False)
				medical_info.patient = patient
				medical_info.save()
				medical_form.save_m2m()
				custom = medical_form.cleaned_data.get("custom_comorbidity")
				if custom:
					comorbidity, _ = Comorbidity.objects.get_or_create(name=custom.strip())
					medical_info.comorbidities.add(comorbidity)
				messages.success(request, "Patient medical info saved from doctor dashboard.")
			else:
				messages.error(request, "Invalid medical info.")

		elif action == "sync_lab_report":
			report = get_object_or_404(LabResult, id=request.POST.get("report_id"))
			process_lab_report_task.delay(report.id)
			messages.success(request, "Lab report sync requested.")

		doctor_param = f"doctor={doctor_id}" if doctor_id else ""
		appt_param = f"active_appt={active_appt_id}" if active_appt_id else ""
		download_param = f"download_rx_id={download_rx_id}" if download_rx_id else ""
		params = [p for p in [doctor_param, appt_param, download_param] if p]
		query = "?" + "&".join(params) if params else ""
		return redirect(f"/doctor-dashboard/{query}")

	if doctor_id:
		selected_doctor = get_object_or_404(Doctor, id=doctor_id)

	appointments = _doctor_queryset(doctor_id)
	attending = appointments.filter(status="I")
	attended = appointments.filter(status="A")
	waiting = appointments.filter(status="T")

	search_q = request.GET.get("search_q", "").strip()
	search_results = None
	if search_q:
		from django.db.models import Q
		search_results = PatientProfile.objects.select_related("filerecord").filter(
			Q(first_name__icontains=search_q) |
			Q(last_name__icontains=search_q) |
			Q(contact_no__icontains=search_q) |
			Q(filerecord__internal_file_number__icontains=search_q) |
			Q(filerecord__external_file_number__icontains=search_q)
		).distinct()

	from clinic.models import ClinicSettings
	settings_obj = ClinicSettings.objects.first()
	api_access_token = settings_obj.api_access_token if settings_obj else ""

	context = {
		"doctor_id": doctor_id,
		"search_q": search_q,
		"doctor_form": DoctorFilterForm(initial={"doctor": doctor_id}),
		"selected_doctor": selected_doctor,
		"appointments": appointments,
		"attending": attending,
		"attended": attended,
		"waiting": waiting,
		"consult_form": ConsultationForm(),
		"prescription_form": PrescriptionForm(),
		"diagnosis_form": PatientDiagnosisForm(),
		"medical_form": PatientMedicalInfoForm(),
		"vitals_form": VitalsForm(),
		"recent_patients": PatientProfile.objects.select_related("filerecord").order_by("-id")[:20],
		"lab_reports": LabResult.objects.select_related("patient__filerecord", "appointment")[:20],
		"search_results": search_results,
		"common_tests": LabTest.objects.filter(is_common=True),
		"api_access_token": api_access_token,
	}
	return render(request, "treatment/doctor_dashboard.html", context)


@login_required(login_url='login')
def joint_chart_page(request, appointment_id):

	appointment = get_object_or_404(Appointment.objects.select_related("patient", "doctor"), id=appointment_id)
	patient = appointment.patient

	latest_chart = (
		jointspain.objects.filter(patient_link=patient)
		.order_by("-date_of_assessment")
		.first()
	)

	if request.method == "POST":
		form = JointPainForm(request.POST)
		if form.is_valid():
			record = form.save(commit=False)
			record.patient_link = patient
			record.save()
			messages.success(request, "Joint chart saved successfully.")
			doctor_id = request.GET.get("doctor") or request.POST.get("doctor_id")
			doc_param = f"doctor={doctor_id}" if doctor_id else ""
			appt_param = f"active_appt={appointment_id}"
			params = [p for p in [doc_param, appt_param] if p]
			query = "?" + "&".join(params)
			return redirect(f"/doctor-dashboard/{query}")
		messages.error(request, "Could not save joint chart. Please review inputs.")
	else:
		initial = {}
		if latest_chart:
			for field_name in JointPainForm().fields.keys():
				initial[field_name] = getattr(latest_chart, field_name)
		form = JointPainForm(initial=initial)

	recent_charts = jointspain.objects.filter(patient_link=patient).order_by("-date_of_assessment")[:6]
	recent_chart_rows = []
	for chart in recent_charts:
		swollen = 0
		tender = 0
		for field in chart._meta.fields:
			name = field.name
			if name in {"id", "date_of_assessment", "patient_link"}:
				continue
			val = getattr(chart, name)
			if val == "red":
				swollen += 1
			elif val == "blue":
				tender += 1
			elif val == "orange":
				swollen += 1
				tender += 1
		recent_chart_rows.append(
			{
				"recorded_at": chart.date_of_assessment,
				"swollen": swollen,
				"tender": tender,
			}
		)

	context = {
		"appointment": appointment,
		"patient": patient,
		"form": form,
		"latest_chart": latest_chart,
		"recent_charts": recent_chart_rows,
		"doctor_id": request.GET.get("doctor", ""),
	}
	return render(request, "treatment/joint_chart_page.html", context)


def queue_data(request):
	doctor_id = request.GET.get("doctor")
	try:
		doctor_id = int(doctor_id) if doctor_id else None
	except ValueError:
		doctor_id = None

	appointments = _doctor_queryset(doctor_id)
	waiting = appointments.filter(status="T")
	attending = appointments.filter(status="I")
	attended = appointments.filter(status="A")

	return JsonResponse(
		{
			"counts": {
				"waiting": waiting.count(),
				"attending": attending.count(),
				"attended": attended.count(),
				"total": appointments.count(),
			},
			"waiting": [
				{
					"id": item.id,
					"token": item.token_number,
					"patient": item.patient.get_full_name(),
					"doctor": item.doctor.get_full_name() if item.doctor else "Unassigned",
					"status": item.get_status_display(),
				}
				for item in waiting.order_by("token_number")
			],
			"attending": [
				{
					"id": item.id,
					"token": item.token_number,
					"patient": item.patient.get_full_name(),
					"doctor": item.doctor.get_full_name() if item.doctor else "Unassigned",
					"status": item.get_status_display(),
				}
				for item in attending.order_by("token_number")
			],
			"attended": [
				{
					"id": item.id,
					"token": item.token_number,
					"patient": item.patient.get_full_name(),
					"doctor": item.doctor.get_full_name() if item.doctor else "Unassigned",
					"status": item.get_status_display(),
				}
				for item in attended.order_by("-updated_at")
			],
		}
	)


def medicine_autosuggest(request):
	q = (request.GET.get("q") or "").strip()
	if len(q) < 2:
		return JsonResponse({"results": []})

	cache_key = f"medicine_suggest::{q.lower()}"
	cached = cache.get(cache_key)
	if cached is not None:
		return JsonResponse({"results": cached})

	medicines = (
		Medicine.objects.filter(Q(medicine_name__icontains=q) | Q(generic_name__icontains=q))
		.values("id", "medicine_name", "generic_name", "strength", "form")[:10]
	)
	results = list(medicines)
	cache.set(cache_key, results, timeout=60 * 10)
	return JsonResponse({"results": results})


def labtest_autosuggest(request):
	q = (request.GET.get("q") or "").strip()
	if len(q) < 2:
		return JsonResponse({"results": []})

	cache_key = f"labtest_suggest::{q.lower()}"
	cached = cache.get(cache_key)
	if cached is not None:
		return JsonResponse({"results": cached})

	tests = LabTest.objects.filter(name__icontains=q).values("id", "name")[:10]
	results = list(tests)
	cache.set(cache_key, results, timeout=60 * 10)
	return JsonResponse({"results": results})


def das28_score(request, appointment_id):
	data = RheumaAnalyticsService.calculate_das28_score(appointment_id)
	return JsonResponse(data)


def get_diagnosis_status(request, appointment_id):
	appointment = get_object_or_404(Appointment, id=appointment_id)
	patient = appointment.patient
	
	# Fetch latest joint chart
	joint = jointspain.objects.filter(patient_link=patient).order_by("-date_of_assessment").first()
	has_joint_chart = False
	joint_details = "Not filled yet"
	if joint:
		has_joint_chart = True
		swollen = 0
		tender = 0
		for field in joint._meta.fields:
			name = field.name
			if name in {"id", "date_of_assessment", "patient_link"}:
				continue
			val = getattr(joint, name)
			if val == "red":
				swollen += 1
			elif val == "blue":
				tender += 1
			elif val == "orange":
				swollen += 1
				tender += 1
		joint_details = f"{swollen} Swollen, {tender} Tender"

	# Fetch latest symptoms checklist
	rumat = RumatDiagnosis.objects.filter(patient_link=patient).order_by("-id").first()
	has_rumat_checklist = False
	rumat_summary = ""
	if rumat:
		has_rumat_checklist = True
		rumat_summary = rumat.description_t or ""

	# Check if PatientDiagnosis already exists for this consultation
	consultation = Consultation.objects.filter(appointment=appointment).first()
	existing_diag = None
	if consultation:
		existing_diag = PatientDiagnosis.objects.filter(consultation_link=consultation).first()

	return JsonResponse({
		"patient_id": patient.id,
		"patient_name": patient.get_full_name(),
		"token_number": appointment.token_number,
		"has_joint_chart": has_joint_chart,
		"joint_details": joint_details,
		"has_rumat_checklist": has_rumat_checklist,
		"rumat_summary": rumat_summary,
		"disease_name": existing_diag.disease_name if existing_diag else "",
		"state": existing_diag.state if existing_diag else "Active",
		"version_note": existing_diag.version_note if existing_diag else "",
	})


def get_patient_medical_info(request, patient_id):
	patient = get_object_or_404(PatientProfile, id=patient_id)
	medical_info = PatientMedicalInfo.objects.filter(patient=patient).first()
	if not medical_info:
		return JsonResponse({
			"exists": False,
			"blood_group": "",
			"family_history": "",
			"known_allergies": "",
			"smokes": False,
			"alcoholic": False,
			"comorbidities": [],
			"comorbidity_names": [],
		})

	return JsonResponse({
		"exists": True,
		"blood_group": medical_info.blood_group,
		"family_history": medical_info.family_history or "",
		"known_allergies": medical_info.known_allergies or "",
		"smokes": medical_info.smokes,
		"alcoholic": medical_info.alcohololic,
		"comorbidities": list(medical_info.comorbidities.values_list("id", flat=True)),
		"comorbidity_names": list(medical_info.comorbidities.values_list("name", flat=True)),
	})


def get_appointment_vitals(request, appointment_id):
	appointment = get_object_or_404(Appointment, id=appointment_id)
	vitals = Vitals.objects.filter(appointment=appointment).first()
	if not vitals:
		return JsonResponse({
			"exists": False,
			"weight": "",
			"height": "",
			"bp_systolic": "",
			"bp_diastolic": "",
			"pulse_rate": "",
			"spo2": "",
			"temperature": "",
			"pain_scale": "",
		})

	return JsonResponse({
		"exists": True,
		"weight": vitals.weight or "",
		"height": vitals.height or "",
		"bp_systolic": vitals.bp_systolic or "",
		"bp_diastolic": vitals.bp_diastolic or "",
		"pulse_rate": vitals.pulse_rate or "",
		"spo2": vitals.spo2 or "",
		"pain_scale": vitals.pain_scale or "",
	})


@login_required(login_url='login')
def rumat_diagnosis_page(request, appointment_id):

	appointment = get_object_or_404(Appointment.objects.select_related("patient", "doctor"), id=appointment_id)
	patient = appointment.patient

	latest_diagnosis = RumatDiagnosis.objects.filter(patient_link=patient).last()

	if request.method == "POST":
		form = RumatDiagnosisForm(request.POST)
		if form.is_valid():
			rumat_diag = form.save(commit=False)
			rumat_diag.patient_link = patient
			rumat_diag.save()

			# Link to PatientDiagnosis / Consultation
			consultation = Consultation.objects.filter(appointment=appointment).first()
			if not consultation:
				consultation = Consultation.objects.create(patient=patient, appointment=appointment)

			patient_diag = PatientDiagnosis.objects.filter(consultation_link=consultation).first()
			if not patient_diag:
				patient_diag = PatientDiagnosis(
					patient_link=patient,
					consultation_link=consultation,
					disease_name="Rheumatoid Arthritis",
				)
			patient_diag.rumat_diagnosis = rumat_diag

			# Check description text for provisional disease mapping
			desc_lower = (rumat_diag.description_t or "").lower()
			if "lupus" in desc_lower or "sle" in desc_lower:
				patient_diag.disease_name = "Lupus (SLE)"
			elif "gout" in desc_lower:
				patient_diag.disease_name = "Gout"
			elif "ankylosing" in desc_lower:
				patient_diag.disease_name = "Ankylosing Spondylitis"
			elif "psoriatic" in desc_lower:
				patient_diag.disease_name = "Psoriatic Arthritis"

			# Allow manual overrides if sent
			if request.POST.get("disease_name"):
				patient_diag.disease_name = request.POST.get("disease_name")
			if request.POST.get("state"):
				patient_diag.state = request.POST.get("state")
			if request.POST.get("version_note"):
				patient_diag.version_note = request.POST.get("version_note")

			patient_diag.save()
			messages.success(request, "Rheumat Diagnosis saved successfully.")
			doctor_id = request.GET.get("doctor") or request.POST.get("doctor_id")
			doc_param = f"doctor={doctor_id}" if doctor_id else ""
			appt_param = f"active_appt={appointment_id}"
			params = [p for p in [doc_param, appt_param] if p]
			query = "?" + "&".join(params)
			return redirect(f"/doctor-dashboard/{query}")
		else:
			messages.error(request, "Failed to save Rheumat Diagnosis. Please check errors.")
	else:
		initial = {}
		if latest_diagnosis:
			for field in RumatDiagnosisForm().fields.keys():
				initial[field] = getattr(latest_diagnosis, field)
		form = RumatDiagnosisForm(initial=initial)

	latest_lab = LabResult.objects.filter(patient=patient).exclude(test_data={}).first()
	latest_lab_data_json = json.dumps(latest_lab.test_data) if (latest_lab and latest_lab.test_data) else "{}"

	context = {
		"appointment": appointment,
		"patient": patient,
		"form": form,
		"doctor_id": request.GET.get("doctor", ""),
		"latest_diagnosis": latest_diagnosis,
		"latest_lab_data_json": latest_lab_data_json,
	}
	return render(request, "treatment/rumat_diagnosis_page.html", context)






from django.views.decorators.clickjacking import xframe_options_sameorigin

@xframe_options_sameorigin
def download_prescription_pdf(request, prescription_id):
	"""
	Downloads or displays the prescription PDF directly, resolving it from the S3/MinIO or local storage backend.
	Generates PDF on-demand if background generation is still pending.
	"""
	from django.shortcuts import get_object_or_404
	from django.http import HttpResponse, Http404
	from django.core.files.base import ContentFile
	from .models import Prescription
	
	prescription = get_object_or_404(Prescription, id=prescription_id)
	if not prescription.prescription_pdf:
		try:
			pdf_bytes = _generate_prescription_pdf(prescription)
			prescription.prescription_pdf.save(
				f"rx_{prescription.consultation_id}.pdf",
				ContentFile(pdf_bytes),
				save=True,
			)
		except Exception as e:
			raise Http404(f"Prescription PDF generation in progress or failed: {e}")
		
	try:
		with prescription.prescription_pdf.open('rb') as f:
			response = HttpResponse(f.read(), content_type='application/pdf')
			response['Content-Disposition'] = f'inline; filename="prescription_{prescription_id}.pdf"'
			return response
	except Exception as e:
		raise Http404(f"Error reading PDF file: {e}")


def prescription_preview(request, prescription_id):
	"""Renders the prescription preview page for the doctor, showing the PDF and option to send to patient."""
	from django.shortcuts import get_object_or_404, render
	from .models import Prescription
	from clinic.models import ClinicSettings

	prescription = get_object_or_404(Prescription, id=prescription_id)
	patient = prescription.consultation.patient
	doctor = prescription.consultation.appointment.doctor if prescription.consultation.appointment else None
	clinic = ClinicSettings.objects.first()

	context = {
		"prescription": prescription,
		"patient": patient,
		"doctor": doctor,
		"clinic": clinic,
	}
	return render(request, "treatment/prescription_preview.html", context)


@csrf_exempt
def send_prescription_to_patient(request, prescription_id):
	"""API endpoint to trigger the Celery task sending the prescription PDF via WhatsApp."""
	from django.shortcuts import get_object_or_404
	from django.http import JsonResponse
	from .models import Prescription
	from clinic.models import ClinicSettings
	from whatsapp.tasks import send_whatsapp_file

	if request.method != "POST":
		return JsonResponse({"ok": False, "error": "Only POST requests are allowed"}, status=405)

	prescription = get_object_or_404(Prescription, id=prescription_id)
	
	if not prescription.prescription_pdf:
		return JsonResponse({"ok": False, "error": "Prescription PDF has not been generated yet"}, status=400)

	patient = prescription.consultation.patient
	patient_phone = patient.contact_no

	if not patient_phone:
		return JsonResponse({"ok": False, "error": "Patient does not have a contact number registered"}, status=400)

	doctor_name = "your doctor"
	if prescription.consultation.appointment and prescription.consultation.appointment.doctor:
		doctor_name = prescription.consultation.appointment.doctor.name

	clinic_name = "RheumaLink Clinic"
	clinic = ClinicSettings.objects.first()
	if clinic and clinic.name:
		clinic_name = clinic.name

	patient_name = f"{patient.first_name} {patient.last_name}"

	caption = (
		f"Intended for - {patient_name}\n\n"
		f"Here is the report of your today's consultation with {doctor_name}.\n\n"
		f"Stay healthy, stay happy!\n\n"
		f"Best regards,\n"
		f"{clinic_name}"
	)

	# Trigger Celery task
	send_whatsapp_file.delay(
		file_path=prescription.prescription_pdf.name,
		file_name=f"prescription_{prescription.id}.pdf",
		caption=caption,
		phone_number=patient_phone,
		bucket_name=prescription.prescription_pdf.storage.bucket_name if hasattr(prescription.prescription_pdf.storage, 'bucket_name') else None
	)

	return JsonResponse({"ok": True, "message": "Prescription sending task dispatched successfully"})


@login_required(login_url='login')
def upload_lab_report_page(request):

	"""Renders the single page lab report upload and extraction playground."""
	return render(request, "treatment/upload_lab_report.html")


@csrf_exempt
def api_upload_lab_report_temp(request):
	"""AJAX view to upload PDF locally and queue the Celery MinIO/LLM task."""
	if request.method != "POST":
		return JsonResponse({"ok": False, "error": "Only POST allowed"}, status=405)
		
	patient_id = request.POST.get("patient_id")
	appointment_id = request.POST.get("appointment_id")
	report_name = request.POST.get("report_name")
	test_date = request.POST.get("test_date")
	pdf_file = request.FILES.get("file")
	
	if not patient_id or not report_name or not pdf_file:
		return JsonResponse({"ok": False, "error": "Missing required fields (patient_id, report_name, file)"}, status=400)
		
	# Save the file temporarily in media root
	from django.conf import settings
	from django.core.files.storage import FileSystemStorage
	import os
	
	temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
	os.makedirs(temp_dir, exist_ok=True)
	
	fs = FileSystemStorage(location=temp_dir, base_url=settings.MEDIA_URL + 'temp_uploads/')
	filename = fs.save(pdf_file.name, pdf_file)
	temp_file_path = fs.path(filename)
	temp_pdf_url = fs.url(filename)
	
	# Trigger Celery task
	from .tasks import process_lab_report_pipeline_task
	task = process_lab_report_pipeline_task.delay(
		patient_id=patient_id,
		appointment_id=appointment_id if appointment_id else None,
		report_name=report_name,
		test_date_str=test_date if test_date else None,
		temp_file_path=temp_file_path
	)
	
	return JsonResponse({
		"ok": True,
		"task_id": task.id,
		"temp_pdf_url": temp_pdf_url
	})


def api_lab_report_task_status(request, task_id):
	"""AJAX view to poll Celery task state and return results upon completion."""
	from celery.result import AsyncResult
	res = AsyncResult(task_id)
	if res.ready():
		if res.successful():
			return JsonResponse({"status": "SUCCESS", "result": res.result})
		else:
			return JsonResponse({"status": "FAILURE", "error": str(res.result)})
	else:
		return JsonResponse({"status": "PROCESSING"})


@csrf_exempt
def api_save_extracted_lab_data(request, report_id):
	"""AJAX view to update test_data in LabResult after compounder/doctor verification."""
	if request.method != "POST":
		return JsonResponse({"ok": False, "error": "Only POST allowed"}, status=405)
		
	import json
	try:
		report = get_object_or_404(LabResult, id=report_id)
		body = json.loads(request.body)
		test_data = body.get("test_data", {})
		
		# Format expected back to: {"test_name": {"value": val, "unit": unit}}
		report.test_data = test_data
		report.is_verified = True
		report.save()
		return JsonResponse({"ok": True})
	except Exception as e:
		return JsonResponse({"ok": False, "error": str(e)}, status=500)


def api_patient_appointments(request, patient_id):
	"""AJAX view to retrieve list of patient appointments for timeline selection."""
	patient = get_object_or_404(PatientProfile, id=patient_id)
	appointments = Appointment.objects.filter(patient=patient).order_by('-appointment_date', '-appointment_time')
	data = []
	for appt in appointments:
		data.append({
			"id": appt.id,
			"date": appt.appointment_date.strftime('%Y-%m-%d'),
			"time": appt.appointment_time.strftime('%H:%M') if appt.appointment_time else "",
			"doctor": appt.doctor.name if appt.doctor else "Unassigned",
			"reason": appt.reason_for_visit or ""
		})
	return JsonResponse({"ok": True, "appointments": data})


def api_patient_search(request):
	"""AJAX view to search patients by name, phone, or file numbers."""
	q = request.GET.get("q", "").strip()
	if not q:
		return JsonResponse({"ok": True, "patients": []})
	from django.db.models import Q
	patients = PatientProfile.objects.select_related("filerecord").filter(
		Q(first_name__icontains=q) |
		Q(last_name__icontains=q) |
		Q(contact_no__icontains=q) |
		Q(filerecord__internal_file_number__icontains=q) |
		Q(filerecord__external_file_number__icontains=q)
	).distinct()[:10]
	
	data = []
	for pat in patients:
		data.append({
			"id": pat.id,
			"name": pat.get_full_name(),
			"phone": pat.contact_no,
			"internal_file": pat.filerecord.internal_file_number if hasattr(pat, 'filerecord') else "-",
			"external_file": pat.filerecord.external_file_number if (hasattr(pat, 'filerecord') and pat.filerecord.external_file_number) else "-"
		})
	return JsonResponse({"ok": True, "patients": data})


@csrf_exempt
def confirm_appointment_api(request):
    """
    API endpoint for compounder to confirm an appointment request.
    Creates PatientProfile, FileRecord, and Appointment in the DB upon approval,
    and sends a WhatsApp confirmation message to the patient.
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST method required"}, status=405)

    import json
    from datetime import datetime, date
    from notification.models import Notification
    from whatsapp.tasks import send_whatsapp_message
    from user.models import User

    try:
        if request.content_type == "application/json":
            data = json.loads(request.body)
        else:
            data = request.POST

        notification_id = data.get("notification_id")
        appointment_id = data.get("appointment_id")
        notif = None

        if notification_id:
            try:
                notif = Notification.objects.get(id=notification_id)
            except Notification.DoesNotExist:
                notif = None

        # Extract parameters from request body or notification json
        msg_json = notif.message_json if (notif and isinstance(notif.message_json, dict)) else {}

        phone = data.get("phone") or msg_json.get("phone", "")
        email = data.get("email") or msg_json.get("email", "")
        full_name = data.get("name") or msg_json.get("name", "")
        first_name = data.get("first_name") or msg_json.get("first_name", "")
        last_name = data.get("last_name") or msg_json.get("last_name", "")

        if full_name and not (first_name or last_name):
            parts = full_name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        doctor_id = data.get("doctor_id") or msg_json.get("doctor_id")
        appt_date_str = data.get("appointment_date") or msg_json.get("appointment_date")
        appt_time_str = data.get("appointment_time") or msg_json.get("appointment_time")
        reason = data.get("reason") or msg_json.get("reason", "")
        notes = data.get("notes") or msg_json.get("notes", "")
        sex = data.get("sex") or msg_json.get("sex", "")
        dob = data.get("dob") or msg_json.get("dob", "")

        combined_reason = reason
        if notes and notes not in reason:
            combined_reason = f"{reason} - {notes}" if reason else notes

        # 1. Doctor Assignment
        assigned_doctor = None
        if doctor_id:
            try:
                assigned_doctor = Doctor.objects.filter(id=doctor_id).first()
            except (ValueError, TypeError):
                pass
        if not assigned_doctor:
            assigned_doctor = Doctor.objects.first()

        # 2. Get existing appointment or create new patient + appointment
        appointment = None
        if appointment_id:
            try:
                appointment = Appointment.objects.filter(id=appointment_id).first()
            except Exception:
                pass

        if not appointment:
            # Find or Create Patient Profile
            patient = None
            if phone:
                patient = PatientProfile.objects.filter(contact_no=phone).first()
            if not patient and email:
                patient = PatientProfile.objects.filter(email=email).first()

            if patient:
                if first_name and not patient.first_name:
                    patient.first_name = first_name
                if last_name and not patient.last_name:
                    patient.last_name = last_name
                if email and not patient.email:
                    patient.email = email
                if phone and not patient.contact_no:
                    patient.contact_no = phone
                patient.type = 'Regular'
                patient.save()
            else:
                clean_email = email.lower() if email else ""
                if not clean_email:
                    if phone:
                        digits_phone = "".join(filter(str.isdigit, phone))[-10:]
                        clean_email = f"patient_{digits_phone}@sandhirheum.local"
                    else:
                        clean_email = f"patient_{date.today().strftime('%Y%m%d%H%M%S')}@sandhirheum.local"

                base_email = clean_email
                counter = 1
                while User.objects.filter(email=clean_email).exists():
                    parts = base_email.split('@')
                    clean_email = f"{parts[0]}_{counter}@{parts[1]}"
                    counter += 1

                dob_val = None
                if dob:
                    try:
                        dob_val = datetime.strptime(dob, "%Y-%m-%d").date()
                    except ValueError:
                        pass

                patient = PatientProfile.objects.create(
                    email=clean_email,
                    first_name=first_name or "Patient",
                    last_name=last_name or "",
                    contact_no=phone,
                    date_of_birth=dob_val,
                    sex=sex if sex in ['M', 'F', 'O'] else '',
                    type='Regular',
                    role=User.Role.PATIENT
                )

            # Ensure FileRecord exists
            FileRecord.objects.get_or_create(patient=patient)

            # Parse date & time
            appt_date = date.today()
            if appt_date_str:
                try:
                    appt_date = datetime.strptime(appt_date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            appt_time = datetime.now().time().replace(microsecond=0)
            if appt_time_str:
                try:
                    appt_time = datetime.strptime(appt_time_str, "%H:%M").time()
                except ValueError:
                    try:
                        appt_time = datetime.strptime(appt_time_str, "%H:%M:%S").time()
                    except ValueError:
                        pass

            # Create Appointment DB Row
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=assigned_doctor,
                appointment_date=appt_date,
                appointment_time=appt_time,
                reason_for_visit=combined_reason or "General Consultation",
                status='T'  # To Be Attended / Confirmed
            )

        else:
            # Updating existing appointment
            if appt_date_str:
                try:
                    appointment.appointment_date = datetime.strptime(appt_date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass
            if appt_time_str:
                try:
                    appointment.appointment_time = datetime.strptime(appt_time_str, "%H:%M").time()
                except ValueError:
                    pass
            if assigned_doctor:
                appointment.doctor = assigned_doctor
            appointment.status = 'T'
            appointment.save()

        # Mark notification as read and confirmed
        if notif:
            notif.mark_as_read()
            if isinstance(notif.message_json, dict):
                notif.message_json['status'] = 'CONFIRMED'
                notif.message_json['appointment_id'] = appointment.id
                notif.save(update_fields=['message_json'])

        # Broadcast live queue update
        if appointment.doctor:
            _broadcast_queue_update(appointment.doctor.id)
        else:
            _broadcast_queue_update()

        patient = appointment.patient
        return JsonResponse({
            "status": "success",
            "message": f"Appointment #{appointment.token_number} approved for {patient.get_full_name()}!",
            "token_number": appointment.token_number,
            "patient_name": patient.get_full_name(),
            "appointment_date": appointment.appointment_date.strftime("%Y-%m-%d"),
            "appointment_time": appointment.appointment_time.strftime("%H:%M")
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


