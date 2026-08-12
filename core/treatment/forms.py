from django import forms

from doctor.models import Doctor
from user.models import User
from patient.models import Comorbidity, PatientDiagnosis, PatientMedicalInfo, PatientProfile
from .models import (
    Appointment,
    Consultation,
    LabResult,
    Prescription,
    Vitals,
    jointspain,
    RumatDiagnosis,
)

import uuid

class PatientProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False
        self.fields["first_name"].required = True

    class Meta:
        model = PatientProfile
        fields = [
            "first_name",
            "last_name",
            "date_of_birth",
            "sex",
            "contact_no",
            "email",
            "type",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and email.strip():
            email = email.strip().lower()
            qs = User.objects.filter(email=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A user with this email address already exists.")
            return email
        else:
            contact_no = self.cleaned_data.get("contact_no", "").strip()
            clean_contact = "".join(filter(str.isalnum, contact_no))
            if clean_contact:
                generated = f"patient_{clean_contact}@rheumalink.local"
                if not User.objects.filter(email=generated).exists():
                    return generated
            unique_suffix = str(uuid.uuid4())[:8]
            return f"patient_{unique_suffix}@rheumalink.local"


class AppointmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = PatientProfile.objects.select_related("filerecord").all()
        self.fields["appointment_time"].required = False

    class Meta:
        model = Appointment
        fields = [
            "patient",
            "doctor",
            "appointment_date",
            "appointment_time",
            "status",
            "reason_for_visit",
        ]
        widgets = {
            "appointment_date": forms.DateInput(attrs={"type": "date"}),
            "appointment_time": forms.TimeInput(attrs={"type": "time"}),
            "reason_for_visit": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_appointment_time(self):
        t = self.cleaned_data.get("appointment_time")
        if not t:
            from datetime import datetime
            return datetime.now().time()
        return t


class AppointmentUpdateForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["doctor", "status"]


class VitalsForm(forms.ModelForm):
    class Meta:
        model = Vitals
        fields = [
            "weight",
            "height",
            "bp_systolic",
            "bp_diastolic",
            "pulse_rate",
            "spo2",
            "temperature",
            "pain_scale",
        ]


class PatientMedicalInfoForm(forms.ModelForm):
    custom_comorbidity = forms.CharField(required=False)

    class Meta:
        model = PatientMedicalInfo
        fields = [
            "blood_group",
            "family_history",
            "known_allergies",
            "smokes",
            "alcoholic",
            "comorbidities",
        ]
        widgets = {
            "family_history": forms.Textarea(attrs={"rows": 2}),
            "known_allergies": forms.Textarea(attrs={"rows": 2}),
            "comorbidities": forms.CheckboxSelectMultiple(),
        }


class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ["chief_complaints", "clinical_findings", "provisional_diagnosis"]
        widgets = {
            "chief_complaints": forms.Textarea(attrs={"rows": 3}),
            "clinical_findings": forms.Textarea(attrs={"rows": 3}),
            "provisional_diagnosis": forms.Textarea(attrs={"rows": 3}),
        }


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ["lab_investigations", "prescribed_tests", "advice_notes", "next_followup_date"]
        widgets = {
            "lab_investigations": forms.Textarea(attrs={"rows": 2}),
            "advice_notes": forms.Textarea(attrs={"rows": 2}),
            "next_followup_date": forms.DateInput(attrs={"type": "date"}),
        }


class LabResultForm(forms.ModelForm):
    class Meta:
        model = LabResult
        fields = ["patient", "appointment", "report_name", "report_file", "test_date"]
        widgets = {
            "test_date": forms.DateInput(attrs={"type": "date"}),
        }


class PatientDiagnosisForm(forms.ModelForm):
    class Meta:
        model = PatientDiagnosis
        fields = ["disease_name", "state", "version_note"]
        widgets = {
            "version_note": forms.Textarea(attrs={"rows": 2}),
        }


class JointPainForm(forms.ModelForm):
    class Meta:
        model = jointspain
        fields = [
            field.name
            for field in jointspain._meta.fields
            if field.name not in {"id", "date_of_assessment", "patient_link"}
            and getattr(field, "choices", None)
        ]
        widgets = {
            field.name: forms.Select(
                choices=jointspain.COLOR_CHOICES,
                attrs={"class": "joint-select"},
            )
            for field in jointspain._meta.fields
            if field.name not in {"id", "date_of_assessment", "patient_link"}
            and getattr(field, "choices", None)
        }


class DoctorFilterForm(forms.Form):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.all(),
        required=False,
        empty_label="All Doctors",
    )


class RumatDiagnosisForm(forms.ModelForm):
    class Meta:
        model = RumatDiagnosis
        fields = "__all__"
        exclude = ["patient_link"]
        widgets = {
            "description_t": forms.Textarea(attrs={"rows": 4}),
        }
