from django.db import models
from django.utils.translation import gettext_lazy as _
from user.models import User
from utils.storages import DoctorPhotoStorage, DoctorSignatureStorage


def doctor_photo_upload_path(instance, filename):
    import os
    ext = filename.split('.')[-1]
    name = f"doctor_{instance.id or 'profile'}.{ext}"
    return os.path.join("photos", name)


def doctor_signature_upload_path(instance, filename):
    import os
    ext = filename.split('.')[-1]
    name = f"doctor_signature_{instance.id or 'profile'}.{ext}"
    return os.path.join("signatures", name)


class Doctor(User):
    photo = models.ImageField(
        upload_to=doctor_photo_upload_path,
        storage=DoctorPhotoStorage(),
        blank=True,
        null=True,
        help_text="Profile photo of the doctor",
        verbose_name="Doctor Photo",
    )
    signature = models.ImageField(
        upload_to=doctor_signature_upload_path,
        storage=DoctorSignatureStorage(),
        blank=True,
        null=True,
        help_text="Signature image of the doctor",
        verbose_name="Doctor Signature",
    )
    contact_no = models.CharField(max_length=20, help_text="Contact number of the doctor", verbose_name="Contact Number")
    highest_qualification = models.CharField(max_length=255, help_text="Highest qualification of the doctor", verbose_name="Highest Qualification")
    specialization = models.CharField(max_length=255, help_text="Specialization of the doctor", verbose_name="Specialization")
    years_of_experience = models.IntegerField(help_text="Years of experience of the doctor", default=0)

    def save(self, *args, **kwargs):
        self.role = User.Role.DOCTOR
        super().save(*args, **kwargs)

    def get_full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        if not full:
            full = self.email.split('@')[0] if self.email else ""
        if full.startswith("Dr. "):
            return full
        return f"Dr. {full}"

    @property
    def name(self):
        return self.get_full_name()

    def __str__(self):
        return self.get_full_name()


class Compounder(User):
    SHIFT_CHOICES = [
        ('Morning', 'Morning'),
        ('Evening', 'Evening'),
        ('Night', 'Night'),
        ('Full Day', 'Full Day'),
    ]

    contact_no = models.CharField(max_length=20, help_text="Contact number of the compounder", verbose_name="Contact Number")
    qualification = models.CharField(max_length=255, help_text="Qualification / Certification (e.g., D.Pharm, B.Pharm)", verbose_name="Qualification", blank=True)
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES, default='Full Day', help_text="Assigned work shift")
    assigned_doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name="compounders", help_text="Assigned doctor in the clinic")
    is_head_compounder = models.BooleanField(default=False, help_text="Designates whether this is the head compounder")

    def save(self, *args, **kwargs):
        self.role = User.Role.COMPOUNDER
        super().save(*args, **kwargs)

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return f"Compounder: {full_name or self.email}"