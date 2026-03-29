from datetime import date

from django.db import models


# Create your models here.
class PatientProfile(models.Model):
    SEX_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    TYPE_CHOICES = [
        ('Regular', 'Regular'),
        ('Free', 'Free'),
    ]

    first_name = models.CharField(max_length=255, help_text="First name of the patient", verbose_name="First Name")
    last_name = models.CharField(max_length=255, help_text="Last name of the patient", verbose_name="Last Name")    
    date_of_birth = models.DateField(help_text="Date of birth of the patient", verbose_name="Date of Birth")
    sex = models.CharField(max_length=1, choices=SEX_CHOICES, help_text="Sex of the patient", verbose_name="Sex")
    contact_no = models.CharField(max_length=20, help_text="Contact number of the patient", verbose_name="Contact Number")
    email = models.EmailField(help_text="Email address of the patient", verbose_name="Email Address")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, help_text="Type of the patient", verbose_name="Type")
    date_registered = models.DateField(auto_now_add=True, help_text="Date when the patient was registered", verbose_name="Date Registered") 

    def __str__(self):
        return f"{self.first_name} {self.last_name} {self.type}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_age(self):
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
    



    

