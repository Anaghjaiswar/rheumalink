from datetime import date
from django.db import models
from user.models import User


class PatientProfile(User):
    SEX_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    TYPE_CHOICES = [
        ('Regular', 'Regular'),
        ('Free', 'Free'),
    ]

    date_of_birth = models.DateField(help_text="Date of birth of the patient", verbose_name="Date of Birth", null=True, blank=True)
    sex = models.CharField(max_length=1, choices=SEX_CHOICES, help_text="Sex of the patient", verbose_name="Sex", blank=True)
    contact_no = models.CharField(max_length=20, help_text="Contact number of the patient", verbose_name="Contact Number", blank=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='Regular', help_text="Type of the patient", verbose_name="Type")
    date_registered = models.DateField(auto_now_add=True, help_text="Date when the patient was registered", verbose_name="Date Registered") 

    def save(self, *args, **kwargs):
        self.role = User.Role.PATIENT
        super().save(*args, **kwargs)

    def __str__(self):
        file_num = ""
        if hasattr(self, 'filerecord') and self.filerecord.internal_file_number:
            file_num = f" ({self.filerecord.internal_file_number})"
        full_name = self.get_full_name() or self.email
        return f"{full_name}{file_num} - {self.type}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        age = today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return age

    

class FileRecord(models.Model):
    """for a patient we will have one fle record/folder where we will store all the files related to that patient"""
    patient = models.OneToOneField(PatientProfile, on_delete=models.CASCADE, help_text="Patient associated with the file record", verbose_name="Patient")
    internal_file_number = models.CharField(max_length=20, unique=True, help_text="Internal file number for the patient", verbose_name="Internal File Number")
    # Note: external_file_number is optional, old file record or compounder generated, in most cases it will be blank
    external_file_number = models.CharField(max_length=20, unique=True, help_text="External file number for the patient", verbose_name="External File Number", blank=True, null=True)

    def __str__(self):
        return f"File Record for {self.patient.get_full_name()} (Internal: {self.internal_file_number})"
    
    def generate_internal_file_number(self):
        """
        Generate a unique internal file number based on the patient's ID and registration date    
        Format: RL-YY-XXXXX (RL for Record, YY for year, XXXXX for zero-padded patient ID)
        """

        year = date.today().strftime("%y")
        last_record = FileRecord.objects.all().order_by('id').last()
        if not last_record:
            new_id = 1
        else:
            new_id = last_record.id + 1

        self.internal_file_number = f"RL-{year}-{new_id:05d}"
        return self.internal_file_number
    
    def save(self, *args, **kwargs):
        if not self.internal_file_number:
            self.generate_internal_file_number()
        super().save(*args, **kwargs)


class Comorbidity(models.Model):
    name = models.CharField(max_length=255, help_text="Name of the comorbidity", verbose_name="Comorbidity Name")

    def __str__(self):
        return self.name


class PatientMedicalInfo(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]

    patient = models.OneToOneField(PatientProfile, on_delete=models.CASCADE, help_text="Patient associated with the medical information", verbose_name="Patient")
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, help_text="Blood group of the patient", verbose_name="Blood Group")   
    family_history = models.TextField(help_text="Family medical history of the patient", verbose_name="Family History", blank=True, null=True)
    known_allergies = models.TextField(help_text="Known allergies of the patient", verbose_name="Known Allergies", blank=True, null=True)
    smokes = models.BooleanField(help_text="Whether the patient smokes or not", verbose_name="Smokes")
    alcohololic = models.BooleanField(help_text="Whether the patient is an alcoholic or not", verbose_name="Alcoholic")
    comorbidities = models.ManyToManyField(Comorbidity, help_text="Comorbidities of the patient", verbose_name="Comorbidities", blank=True)

    def __str__(self):
        return f"Medical Information for {self.patient.get_full_name()} | Blood Group: {self.blood_group}"
    
class PatientDiagnosis(models.Model):
    """
    The 'Book' of diagnosis history for a patient.
    Every save is a new page in the timeline.
    """
    from treatment.models import Consultation, jointspain, RumatDiagnosis
    STATE_CHOICES = [
        ('Active', 'Active'),
        ('Remission', 'Remission'),
        ('Stable', 'Stable'),
        ('Worsening', 'Worsening'),
    ]

    patient_link = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name="diagnosis_history")
    consultation_link = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name="diagnosis_records")
    joints_record = models.ForeignKey(jointspain, on_delete=models.SET_NULL, null=True, blank=True)
    rumat_diagnosis = models.ForeignKey(RumatDiagnosis, on_delete=models.SET_NULL, null=True, blank=True)
    
    disease_name = models.CharField(max_length=255, help_text="e.g., Rheumatoid Arthritis, SLE")
    state = models.CharField(max_length=50, choices=STATE_CHOICES, default='Active')
    version_note = models.TextField(blank=True, null=True, help_text="Doctor's notes for this specific version of diagnosis")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Patient Diagnosis"
        verbose_name_plural = "Patient Diagnosis History"

    def __str__(self):
        return f"{self.disease_name} - {self.patient_link} ({self.state})"
    

class PatientQueries(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name="queries")
    query = models.TextField(help_text="Patient's query or concern", verbose_name="Patient Query")
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False, help_text="Whether the query has been resolved or not", verbose_name="Is Resolved")
    ai_generated_response = models.TextField(help_text="AI generated response to the patient's query", verbose_name="AI Generated Response", blank=True, null=True)
    is_ai_response_approved = models.BooleanField(default=False, help_text="Whether the AI generated response has been approved by a doctor", verbose_name="Is AI Response Approved")

    def __str__(self):
        return f"Query by {self.patient.get_full_name()} on {self.created_at}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Patient Query"
        verbose_name_plural = "Patient Queries"


class PatientState(models.Model):
    STATE_CHOICES = [
        ("idle", "Idle"),
        ("awaiting_query", "Awaiting Query"),
    ]

    SESSION_TIMEOUT_MINUTES = 15

    patient = models.OneToOneField(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="whatsapp_state",
        help_text="Current WhatsApp conversation state for the patient",
        verbose_name="Patient",
    )
    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default="idle",
        help_text="Current WhatsApp conversation state",
        verbose_name="State",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    session_started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Patient State"
        verbose_name_plural = "Patient States"

    def __str__(self):
        return f"{self.patient.get_full_name()} - {self.state}"

    def session_is_active(self, now=None):
        from django.utils import timezone

        if self.state != "awaiting_query" or not self.session_started_at:
            return False

        current_time = now or timezone.now()
        elapsed_minutes = (current_time - self.session_started_at).total_seconds() / 60
        return elapsed_minutes <= self.SESSION_TIMEOUT_MINUTES




