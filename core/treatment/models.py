from django.db import models, transaction
from patient.models import PatientProfile
from doctor.models import Doctor
from django.db.models import Max, UniqueConstraint, Q


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('T', 'To Be Attended'),
        ('I', 'In'),
        ('A', 'Attended'),
        ('C', 'Cancelled'),
        ('N', 'No Show/Absent'),
    ]

    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, help_text="Patient associated with the appointment", verbose_name="Patient")
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, help_text="Doctor associated with the appointment", verbose_name="Doctor", null=True, blank=True)
    appointment_date = models.DateField(help_text="Date of the appointment", verbose_name="Appointment Date")
    appointment_time = models.TimeField(help_text="Time of the appointment", verbose_name="Appointment Time")
    token_number = models.PositiveIntegerField(help_text="Token number for the appointment", verbose_name="Token Number")
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, help_text="Status of the appointment", verbose_name="Status")
    reason_for_visit = models.TextField(help_text="Reason for the patient's visit", verbose_name="Reason for Visit", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, help_text="Date and time when the appointment was created", verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, help_text="Date and time when the appointment was last updated", verbose_name="Updated At")

    def __str__(self):
        return f"Appointment for {self.patient.get_full_name()} with Dr. {self.doctor.get_full_name() if self.doctor else 'N/A'} on {self.appointment_date} at {self.appointment_time} | Status: {self.get_status_display()}"
    
    def generate_token_number(self):
        """
        Simpler logic: Works with provided setup. 
        Ensures daily reset and doctor-specific queue.
        """
        max_t = Appointment.objects.filter(
            appointment_date=self.appointment_date,
            doctor=self.doctor
        ).aggregate(Max('token_number'))['token_number__max']
        
        return (max_t or 0) + 1



    def save(self, *args, **kwargs):
        if not self.token_number:
            self.token_number = self.generate_token_number()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['appointment_date', 'appointment_time']
        constraints = [
            # Handle unique token per doctor per day
            UniqueConstraint(
                fields=['appointment_date', 'token_number', 'doctor'], 
                name='unique_appointment_with_doctor'
            ),
            # Handle unique token for 'General Queue' (where doctor is null)
            UniqueConstraint(
                fields=['appointment_date', 'token_number'],
                condition=Q(doctor__isnull=True),
                name='unique_general_appointment_token'
            )
        ]

class Vitals(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, help_text="Patient associated with the vitals", verbose_name="Patient")
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, help_text="Appointment associated with the vitals", verbose_name="Appointment")
    weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Weight of the patient in kg", verbose_name="Weight (kg)", blank=True, null=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, help_text="Height of the patient in cm", verbose_name="Height (cm)", blank=True, null=True)
    bp_systolic = models.PositiveIntegerField(help_text="Systolic blood pressure of the patient", verbose_name="Blood Pressure Systolic (mmHg)", blank=True, null=True)
    bp_diastolic = models.PositiveIntegerField(help_text="Diastolic blood pressure of the patient", verbose_name="Blood Pressure Diastolic (mmHg)", blank=True, null=True)
    pulse_rate = models.PositiveIntegerField(help_text="Pulse rate of the patient", verbose_name="Pulse Rate (bpm)", blank=True, null=True)
    spo2 = models.PositiveIntegerField(help_text="Oxygen saturation level of the patient", verbose_name="SpO2 (%)", blank=True, null=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, help_text="Body temperature of the patient in Celsius", verbose_name="Temperature (°C)", blank=True, null=True)

    def __str__(self):
        return f"Vitals for {self.patient.get_full_name()} on {self.appointment.appointment_date}"

    class Meta:
        verbose_name = "Vitals"
        verbose_name_plural = "Vitals"



def lab_report_upload_path(instance, filename):
    # NOTE:Files will be saved to: media/lab_reports/YYYY/MM/
    return f"lab_reports/{instance.appointment.appointment_date.year}/{instance.appointment.appointment_date.month}/{filename}"


class LabResult(models.Model):
    # ForeignKey: Kyunki ek patient ki zindagi bhar ki reports track karni hain
    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE, 
        related_name="lab_results"
    )
    
    # ForeignKey (NOT OneToOne): Taaki ek appointment mein 5 reports bhi upload ho sakein
    appointment = models.ForeignKey(
        'Appointment', 
        on_delete=models.CASCADE, 
        related_name="lab_reports",
        null=True, blank=True # Nullable taaki purani reports bhi bina appointment ke upload ho sakein
    )

    report_name = models.CharField(max_length=255, help_text="e.g., CBC, Liver Function, ANA Profile")
    report_file = models.FileField(upload_to = lab_report_upload_path)


    # Flexible JSON storage for any test result
    # Format: {"ESR": {"value": 45, "unit": "mm/hr"}, "CRP": {"value": 12, "unit": "mg/L"}}
    test_data = models.JSONField(
        default=dict, 
        help_text="Stores structured results for any test ordered by the doctor"
    )

    # LLM Metadata
    raw_ai_summary = models.JSONField(null=True, blank=True) # LLM ka raw extraction
    is_verified = models.BooleanField(default=False) # Doctor approves AI extraction
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lab Report"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.report_name} - {self.patient.get_full_name()}"

    # Helper method for DAS28 calculation
    def get_marker_value(self, marker_name):
        """Safely extracts a marker (like ESR or CRP) from JSON data"""
        marker = self.test_data.get(marker_name)
        return float(marker['value']) if marker and 'value' in marker else None

class Medicine(models.Model):
    FORM_CHOICES = [
        ('Tablet', 'Tablet'), ('Syrup', 'Syrup'), ('Injection', 'Injection'),
        ('Capsule', 'Capsule'), ('Other', 'Other'),
    ]
    medicine_name = models.CharField(max_length=255, unique=True, verbose_name="Medicine Name")
    generic_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Generic Name")
    form = models.CharField(max_length=20, choices=FORM_CHOICES, blank=True, null=True)
    strength = models.CharField(max_length=50, blank=True, null=True, help_text="eg: 500mg")
    category = models.CharField(max_length=255, blank=True, null=True, db_index=True) # Indexed for filtering

    class Meta:
        verbose_name = "Medicine Master"
        verbose_name_plural = "Medicine Inventory"

    def __str__(self):
        return f"{self.medicine_name} ({self.strength})"


class Consultation(models.Model):
    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE,
        related_name="consultations", verbose_name="Patient"
    )
    appointment = models.OneToOneField(
        'Appointment', on_delete=models.CASCADE, 
        related_name="consultation_record", verbose_name="Appointment"
    )
    chief_complaints = models.TextField(blank=True, null=True, verbose_name="Chief Complaints")
    clinical_findings = models.TextField(blank=True, null=True, verbose_name="Clinical Findings")
    provisional_diagnosis = models.TextField(blank=True, null=True, verbose_name="Provisional Diagnosis")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at'] 

    def __str__(self):
        return f"Consultation - {self.patient.get_full_name()} ({self.created_at.date()})"


def prescription_upload_path(instance, filename):
    # NOTE:Files will be saved to: media/prescriptions/YYYY/MM/filename
    return f"prescriptions/{instance.consultation.created_at.year}/{instance.consultation.created_at.month}/{filename}"


class Prescription(models.Model):
    consultation = models.OneToOneField(
        Consultation, on_delete=models.CASCADE, 
        related_name="prescription", verbose_name="Consultation"
    )
    lab_investigations = models.TextField(blank=True, null=True, verbose_name="Lab Tests")
    advice_notes = models.TextField(blank=True, null=True, verbose_name="General Advice")
    next_followup_date = models.DateField(blank=True, null=True)
    prescription_pdf = models.FileField(
        upload_to=prescription_upload_path, blank=True, null=True
    )

    def __str__(self):
        return f"Rx - {self.consultation.patient.get_full_name()}"
    
class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(
        Prescription, on_delete=models.CASCADE, 
        related_name="items", verbose_name="Prescription"
    )
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT)
    dosage = models.CharField(max_length=255, help_text="eg: 1-0-1", verbose_name="Dosage")
    instructions = models.TextField(blank=True, null=True, verbose_name="Instructions")
    duration = models.CharField(max_length=255, help_text="eg: 7 days", verbose_name="Duration")

    def __str__(self):
        return f"{self.medicine.medicine_name} - {self.dosage}"
    

class jointspain(models.Model):
    COLOR_CHOICES = [
        ('red', 'Swollen'),
        ('blue', 'Tender'),
        ('orange', 'Both Swollen and Tender'),
        ('nopain', 'No Pain')
    ]

    # Define each joint field with the specified choices
    date_of_assessment = models.DateTimeField(auto_now_add=True,auto_now=False)
    patient_link = models.ForeignKey(PatientProfile, related_name="joint_chart_patient", on_delete=models.CASCADE)

    acromioclavicularleft = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    sternoclavicularright = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    sternoclavicularleft = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    shoulderright = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    shoulderleft = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    elbowright = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    elbowleft = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    wristright = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    wristleft = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip5right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip5left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip4right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip4left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp5right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp5left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip3right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip3left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp4right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp4left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip2right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip2left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip1right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    pip1left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp3right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp3left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp2right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp2left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp1right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mcp1left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    kneeright = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    kneeleft = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    ankleright = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    ankleleft = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp5right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp5left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp4right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp4left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp3right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp3left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp2right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp1right = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp1left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    mtp2left = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)
    acromioclavicularright = models.CharField(max_length=10, choices=COLOR_CHOICES, blank=True, null=True)

    def __str__(self):
        return "Joint Colors"

    class Meta:
        verbose_name = "Joint Chart"
        verbose_name_plural = "Joint Charts"
    


class RumatDiagnosis(models.Model):
    patient_link = models.ForeignKey(PatientProfile, related_name="rumat_diagnosis_patient", on_delete=models.CASCADE)
    #==============================================================================================================#
    # musculio-skelital manifestatison
    msm = models.BooleanField(default=False , verbose_name="Is there musculio-skelital manifestatison")
    duration_years_msm = models.IntegerField(null=True,blank=True)
    duration_months_msm = models.IntegerField(null=True,blank=True)
    duration_days_msm = models.IntegerField(null=True,blank=True)
    ji_hand_right_msm = models.BooleanField(default=False, verbose_name="Hand Right Involvement")
    ji_hand_left_msm = models.BooleanField(default=False, verbose_name="Hand Left Involvement")
    ji_wrist_right_msm = models.BooleanField(default=False, verbose_name="Wrist Right Involvement")
    ji_wrist_left_msm = models.BooleanField(default=False, verbose_name="Wrist Left Involvement")
    ji_elbow_right_msm = models.BooleanField(default=False, verbose_name="Elbow Right Involvement")
    ji_elbow_left_msm = models.BooleanField(default=False, verbose_name="Elbow Left Involvement")
    ji_shoulder_right_msm = models.BooleanField(default=False, verbose_name="Shoulder Right Involvement")
    ji_shoulder_left_msm = models.BooleanField(default=False, verbose_name="Shoulder Left Involvement")
    ji_hip_right_msm = models.BooleanField(default=False, verbose_name="Hip Right Involvement")
    ji_hip_left_msm = models.BooleanField(default=False, verbose_name="Hip Left Involvement")
    ji_knee_right_msm = models.BooleanField(default=False, verbose_name="Knee Right Involvement")
    ji_knee_left_msm = models.BooleanField(default=False, verbose_name="Knee Left Involvement")
    ji_ankle_right_msm = models.BooleanField(default=False, verbose_name="Ankle Right Involvement")
    ji_ankle_left_msm = models.BooleanField(default=False, verbose_name="Ankle Left Involvement")
    ji_foot_right_msm = models.BooleanField(default=False, verbose_name="Foot Right Involvement")
    ji_foot_left_msm = models.BooleanField(default=False, verbose_name="Foot Left Involvement")
    symmetricity = models.BooleanField(default=False, verbose_name="symmetricity")
    pattern_addctive_msm = models.BooleanField(default=False, verbose_name="Pattern addctive")
    relapsing_msm = models.BooleanField(default=False, verbose_name="Relapsing")
    episodic_msm = models.BooleanField(default=False, verbose_name="Epospdic")
    lom_hand_right_msm = models.BooleanField(default=False, verbose_name="Hand Right limitation of movement")
    lom_hand_left_msm = models.BooleanField(default=False, verbose_name="Hand Left limitation of movement")
    lom_wrist_right_msm = models.BooleanField(default=False, verbose_name="Wrist Right limitation of movement")
    lom_wrist_left_msm = models.BooleanField(default=False, verbose_name="Wrist Left limitation of movement")
    lom_elbow_right_msm = models.BooleanField(default=False, verbose_name="Elbow Right limitation of movement")
    lom_elbow_left_msm = models.BooleanField(default=False, verbose_name="Elbow Left limitation of movement")
    lom_shoulder_right_msm = models.BooleanField(default=False, verbose_name="Shoulder Right limitation of movement")
    lom_shoulder_left_msm = models.BooleanField(default=False, verbose_name="Shoulder Left limitation of movement")
    lom_hip_right_msm = models.BooleanField(default=False, verbose_name="Hip Right limitation of movement")
    lom_hip_left_msm = models.BooleanField(default=False, verbose_name="Hip Left limitation of movement")
    lom_knee_right_msm = models.BooleanField(default=False, verbose_name="Knee Right limitation of movement")
    lom_knee_left_msm = models.BooleanField(default=False, verbose_name="Knee Left limitation of movement")
    lom_ankle_right_msm = models.BooleanField(default=False, verbose_name="Ankle Right limitation of movement")
    lom_ankle_left_msm = models.BooleanField(default=False, verbose_name="Ankle Left limitation of movement")
    lom_foot_right_msm = models.BooleanField(default=False, verbose_name="Foot Right limitation of movement")
    lom_foot_left_msm = models.BooleanField(default=False, verbose_name="Foot Left limitation of movement")
    #==============================================================================================================#

    #Back ache
    ba = models.BooleanField(default=False, verbose_name="Back Ache")
    duration_years_ba = models.IntegerField(null=True,blank=True)
    duration_months_ba = models.IntegerField(null=True,blank=True)
    duration_days_ba = models.IntegerField(null=True,blank=True)
    early_morning_stiffness_ba =  models.BooleanField(default=False, verbose_name="Early morning stiffness")
    area_involved_low_ba =  models.BooleanField(default=False, verbose_name="Area Involved Low Back Ache")
    area_involved_mid_ba = models.BooleanField(default=False, verbose_name="Area Involved Mid Back Ache")
    area_involved_neck_ba = models.BooleanField(default=False, verbose_name="Area Involved Neck Back Ache")
    area_involved_buttock_ba = models.BooleanField(default=False, verbose_name="Area Involved Buttock Back Ache")
    #==============================================================================================================#
    #weakness
    wk = models.BooleanField(default=False, verbose_name="Weakness")
    description_wk = models.CharField(max_length=255, verbose_name="Description weakness",null=True,blank=True)

    #==============================================================================================================#
    #dermatological
    der = models.BooleanField(default=False, verbose_name="dermatological")
    photosensitivity_der = models.BooleanField(default=False, verbose_name="Photosensitivity")
    malarrash_der = models.BooleanField(default=False, verbose_name="Malar Rash")
    prupura_der = models.BooleanField(default=False, verbose_name="Purpura")
    rec_oral_ulcer_der = models.BooleanField(default=False, verbose_name="Recurrent Oral Ulcer")
    gangrene_der = models.BooleanField(default=False, verbose_name="Gangrene")
    raynauds_phenomenon_der = models.BooleanField(default=False, verbose_name="Raynaud's Phenomenon")
    skin_thickening_der = models.BooleanField(default=False, verbose_name="Skin Thickening")
    dry_mouth_der = models.BooleanField(default=False, verbose_name="Dry Mouth")
    psoriasis_skin_der = models.BooleanField(default=False, verbose_name="Psoriasis Skin")
    psoriasis_scalp_der = models.BooleanField(default=False, verbose_name="Psoriasis Scalp")
    psoriasis_nail_der = models.BooleanField(default=False, verbose_name="Psoriasis Nail")
    hair_loss_der = models.BooleanField(default=False, verbose_name="Hair Loss")
    urticaria_der = models.BooleanField(default=False, verbose_name="Urticaria")

    #==============================================================================================================#
    # Opthalmological fields
    opth = models.BooleanField(default=False, verbose_name="Opthalmological")
    dry_eyes_opth = models.BooleanField(default=False, verbose_name="Dry Eyes")
    scleritis_episcleritis_opth = models.BooleanField(default=False, verbose_name="Scleritis/Episcleritis")
    redness_opth = models.BooleanField(default=False, verbose_name="Redness")
    iridocyclitis_opth = models.BooleanField(default=False, verbose_name="Iridocyclitis")
    bov_opth = models.BooleanField(default=False, verbose_name="B+OV")

    #==============================================================================================================#
    # Constitutional fields
    cons = models.BooleanField(default=False, verbose_name="Constitutional")
    wt_loss_cons = models.BooleanField(default=False, verbose_name="Weight Loss")
    wt_gain_cons = models.BooleanField(default=False, verbose_name="Weight Gain")
    fever_cons = models.BooleanField(default=False, verbose_name="Fever")

    #==============================================================================================================#
    # Allergy fields
    allergy = models.BooleanField(default=False, verbose_name="Allergy")
    description_drugs_allergy = models.CharField(max_length=255, verbose_name="Drugs Allergy",null=True,blank=True)
    description_other_allergy = models.CharField(max_length=255, verbose_name="Other Allergy",null=True,blank=True)

    #==============================================================================================================#
    # Systems fields
    sys = models.BooleanField(default=False, verbose_name="Systems")
    description_cardiorespiratory_sys = models.CharField(max_length=255, verbose_name="Cardiorespiratory",null=True,blank=True)
    description_gastrointestinal_sys = models.CharField(max_length=255, verbose_name="Gastrointestinal",null=True,blank=True)
    description_cns_sys = models.CharField(max_length=255, verbose_name="Central Nervous System",null=True,blank=True)
    description_rs_sys = models.CharField(max_length=255, verbose_name="Respiratory System",null=True,blank=True)

    #==============================================================================================================#
    # Past History fields
    ph = models.BooleanField(default=False, verbose_name="Past History")
    dm_ph = models.BooleanField(default=False, verbose_name="Diabetes Mellitus")
    htn_ph = models.BooleanField(default=False, verbose_name="Hypertension")
    thyroid_ph = models.BooleanField(default=False, verbose_name="Thyroid Disorder")
    ihd_ph = models.BooleanField(default=False, verbose_name="Ischemic Heart Disease")
    seizures_ph = models.BooleanField(default=False, verbose_name="Seizures")
    stroke_ph = models.BooleanField(default=False, verbose_name="Stroke")
    leukoderma_ph = models.BooleanField(default=False, verbose_name="Leukoderma")

    #==============================================================================================================#
    # Obstetric History fields
    oh = models.BooleanField(default=False, verbose_name="Obstetric History")
    description_oh = models.CharField(max_length=255, verbose_name="Description",null=True,blank=True)

    #==============================================================================================================#
    # Personal History fields
    perh = models.BooleanField(default=False, verbose_name="Personal History")
    appetite_normal_perh = models.BooleanField(default=False, verbose_name="Appetite Normal")
    appetite_redused_perh = models.BooleanField(default=False, verbose_name="Appetite Reduced")
    sleep_normal_perh = models.BooleanField(default=False, verbose_name="Sleep Normal")
    sleep_disturbed_perh = models.BooleanField(default=False, verbose_name="Sleep Disturbed")
    smoking_perh = models.BooleanField(default=False, verbose_name="Smoking")
    drinking_perh = models.BooleanField(default=False, verbose_name="Drinking")
    tobacco_perh = models.BooleanField(default=False, verbose_name="Tobacco")

    #==============================================================================================================#
    # Spine Examination fields
    spe = models.BooleanField(default=False, verbose_name="Spine Examination")
    restricted_movement_spe = models.BooleanField(default=False, verbose_name="Restricted Movement")
    description_spe = models.CharField(max_length=255, verbose_name="Description_spe",null=True,blank=True)

    #==============================================================================================================#
    description_t =  models.CharField(max_length=1028, verbose_name="Description_total",null=True,blank=True)
    
    class Meta:
        verbose_name = "RumatDiagnosis"
        verbose_name_plural = "RumatDiagnosis"

    