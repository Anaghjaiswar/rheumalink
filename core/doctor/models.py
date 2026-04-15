from django.db import models

class Doctor(models.Model):
    name = models.CharField(max_length=255, help_text="Name of the doctor", verbose_name="Doctor Name")
    contact_no = models.CharField(max_length=20, help_text="Contact number of the doctor", verbose_name="Contact Number")
    email = models.EmailField(help_text="Email address of the doctor", verbose_name="Email Address")
    highest_qualification = models.CharField(max_length=255, help_text="Highest qualification of the doctor", verbose_name="Highest Qualification")
    specialization = models.CharField(max_length=255, help_text="Specialization of the doctor", verbose_name="Specialization")
    years_of_experience = models.IntegerField(help_text="Years of experience of the doctor")

    def __str__(self):
        return self.name

    def get_full_name(self):
        return self.name