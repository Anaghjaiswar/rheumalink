from datetime import date
from io import BytesIO

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.views.decorators.csrf import csrf_exempt
import requests


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
from .models import Appointment, Consultation, LabResult, Medicine, Prescription, PrescriptionItem, RumatDiagnosis, Vitals, jointspain
from .services import RheumaAnalyticsService
from .tasks import process_lab_report_task


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
	"""Creates a light-weight PDF so doctor can share immediately after consult save."""
	buffer = BytesIO()
	pdf = canvas.Canvas(buffer, pagesize=A4)
	w, h = A4

	patient = prescription.consultation.patient
	consultation = prescription.consultation

	y = h - 50
	pdf.setFont("Helvetica-Bold", 16)
	pdf.drawString(40, y, "RheumaLink Prescription")
	y -= 30

	pdf.setFont("Helvetica", 11)
	pdf.drawString(40, y, f"Patient: {patient.get_full_name()}")
	y -= 18
	pdf.drawString(40, y, f"Date: {consultation.created_at.date()}")
	y -= 18
	pdf.drawString(40, y, f"Consultation ID: {consultation.id}")
	y -= 24

	pdf.setFont("Helvetica-Bold", 12)
	pdf.drawString(40, y, "Medicines")
	y -= 18
	pdf.setFont("Helvetica", 10)

	items = prescription.items.select_related("medicine").all()
	if not items:
		pdf.drawString(40, y, "No medicine added")
		y -= 16
	else:
		for idx, item in enumerate(items, 1):
			line = (
				f"{idx}. {item.medicine.medicine_name} | Dosage: {item.dosage} | "
				f"Duration: {item.duration}"
			)
			pdf.drawString(40, y, line[:110])
			y -= 16
			if item.instructions:
				pdf.drawString(60, y, f"Instructions: {item.instructions[:100]}")
				y -= 16
			if y < 80:
				pdf.showPage()
				y = h - 50

	y -= 8
	pdf.setFont("Helvetica-Bold", 12)
	pdf.drawString(40, y, "Advice")
	y -= 18
	pdf.setFont("Helvetica", 10)
	pdf.drawString(40, y, (prescription.advice_notes or "-")[:120])
	y -= 18
	pdf.drawString(40, y, f"Lab Investigations: {(prescription.lab_investigations or '-')[:95]}")
	y -= 18
	pdf.drawString(40, y, f"Next Follow-up: {prescription.next_followup_date or '-'}")

	pdf.showPage()
	pdf.save()
	return buffer.getvalue()


def _doctor_queryset(doctor_id):
	base = Appointment.objects.select_related("patient__filerecord", "doctor").filter(appointment_date=date.today())
	if doctor_id:
		base = base.filter(doctor_id=doctor_id)
	return base


def compounder_dashboard(request):
	if request.method == "POST":
		action = request.POST.get("action")

		if action == "register_patient":
			patient_form = PatientProfileForm(request.POST)
			if patient_form.is_valid():
				patient = patient_form.save()
				ext_num = request.POST.get("external_file_number", "").strip() or None
				FileRecord.objects.get_or_create(patient=patient, defaults={"external_file_number": ext_num})
				messages.success(request, "Patient profile and file record created.")
			else:
				messages.error(request, "Could not create patient profile.")

		elif action == "create_appointment":
			appointment_form = AppointmentForm(request.POST)
			if appointment_form.is_valid():
				appointment = appointment_form.save()
				messages.success(request, f"Appointment created with token {appointment.token_number}.")
				_broadcast_queue_update(appointment.doctor_id)
			else:
				messages.error(request, "Appointment creation failed.")

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
			else:
				messages.error(request, "Invalid vitals data.")

		elif action == "update_appointment":
			appointment = get_object_or_404(Appointment, id=request.POST.get("appointment_id"))
			update_form = AppointmentUpdateForm(request.POST, instance=appointment)
			if update_form.is_valid():
				updated = update_form.save()
				messages.success(request, "Appointment updated.")
				_broadcast_queue_update(updated.doctor_id)
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
			else:
				messages.error(request, "Medical info is invalid.")

		elif action == "upload_lab_report":
			report_form = LabResultForm(request.POST, request.FILES)
			if report_form.is_valid():
				report_form.save()
				messages.success(request, "Lab report uploaded.")
			else:
				messages.error(request, "Lab report upload failed.")

		elif action == "sync_lab_report":
			report = get_object_or_404(LabResult, id=request.POST.get("report_id"))
			process_lab_report_task.delay(report.id)
			messages.success(request, "Lab report sync triggered on primary worker.")

		return redirect("compounder-dashboard")

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
		"patient_form": PatientProfileForm(),
		"appointment_form": AppointmentForm(initial={"status": "T"}),
		"vitals_form": VitalsForm(),
		"medical_form": PatientMedicalInfoForm(),
		"report_form": LabResultForm(),
		"today_appointments": today_appointments,
		"recent_patients": PatientProfile.objects.select_related("filerecord").order_by("-id")[:10],
		"pending_reports": LabResult.objects.select_related("patient__filerecord", "appointment")[:10],
		"search_results": search_results,
		"is_recent_list": is_recent_list,
	}
	return render(request, "treatment/compounder_dashboard.html", context)


def doctor_dashboard(request):
	doctor_id = request.GET.get("doctor") or request.POST.get("doctor_id")
	selected_doctor = None
	if doctor_id:
		try:
			doctor_id = int(doctor_id)
		except (TypeError, ValueError):
			doctor_id = None

	if request.method == "POST":
		action = request.POST.get("action")
		active_appt_id = request.POST.get("active_appt_id") or request.POST.get("appointment_id")

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

				pdf_bytes = _generate_prescription_pdf(prescription)
				prescription.prescription_pdf.save(
					f"rx_{consultation.id}.pdf",
					ContentFile(pdf_bytes),
					save=True,
				)

				appointment.status = request.POST.get("post_consult_status") or appointment.status
				appointment.save(update_fields=["status", "updated_at"])
				_broadcast_queue_update(appointment.doctor_id)
				messages.success(request, "Consultation, prescription, and PDF saved.")
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
		params = [p for p in [doctor_param, appt_param] if p]
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

	context = {
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
	}
	return render(request, "treatment/doctor_dashboard.html", context)


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
			doctor_id = request.GET.get("doctor")
			query = f"?doctor={doctor_id}" if doctor_id else ""
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
			doctor_id = request.GET.get("doctor")
			query = f"?doctor={doctor_id}" if doctor_id else ""
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
	latest_lab_data = latest_lab.test_data if latest_lab else {}

	context = {
		"appointment": appointment,
		"patient": patient,
		"form": form,
		"doctor_id": request.GET.get("doctor", ""),
		"latest_diagnosis": latest_diagnosis,
		"latest_lab_data": latest_lab_data,
	}
	return render(request, "treatment/rumat_diagnosis_page.html", context)



@csrf_exempt
def generate_rumat_summary(request, appointment_id):
	if request.method != "POST":
		from django.http import JsonResponse
		return JsonResponse({"error": "Only POST requests allowed"}, status=405)

	try:
		import json
		from django.http import StreamingHttpResponse, JsonResponse
		from clinic.models import ClinicSettings
		
		appointment = get_object_or_404(Appointment.objects.select_related("patient"), id=appointment_id)
		patient = appointment.patient
		
		body = json.loads(request.body)
		findings = body.get("findings", {})

		# Retrieve clean data directly from DB
		age = patient.get_age()
		sex = patient.sex
		sex_str = "male" if sex == "M" else "female"

		settings = ClinicSettings.objects.first()

		if not settings or not settings.is_ai_enabled:
			def stream_unsubscribed():
				yield "⚠️ AI Summary Service is not active. Please subscribe to enable this feature."
			return StreamingHttpResponse(stream_unsubscribed(), content_type="text/plain")

		try:
			# Call actual AI Service configured in sample.py on port 8001 (Streaming)
			AI_URL = "http://ai_service:8001/v1/rumat-summary"
			headers = {
				"X-Clinic-Key": settings.api_access_token,
				"Content-Type": "application/json"
			}
			payload = {
				"age": age,
				"sex": sex_str,
				"findings": findings
			}
			response = requests.post(AI_URL, json=payload, headers=headers, timeout=15, stream=True)
			if response.status_code == 200:
				def stream_response():
					for chunk in response.iter_content(chunk_size=512, decode_unicode=True):
						if chunk:
							yield chunk
				return StreamingHttpResponse(stream_response(), content_type="text/plain")
			else:
				def stream_api_error():
					yield f"⚠️ AI Service returned error {response.status_code}. Please contact support."
				return StreamingHttpResponse(stream_api_error(), content_type="text/plain")
		except Exception:
			def stream_conn_error():
				yield "⚠️ AI Service is temporarily unreachable. Please check your connection and try again."
			return StreamingHttpResponse(stream_conn_error(), content_type="text/plain")

	except Exception as e:
		from django.http import JsonResponse
		return JsonResponse({"error": str(e)}, status=500)

