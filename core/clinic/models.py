from django.db import models

# Create your models here.

class Address(models.Model):
    line1 = models.CharField(max_length=255, help_text="Address Line 1", verbose_name="Address Line 1")
    line2 = models.CharField(max_length=255, help_text="Address Line 2", verbose_name="Address Line 2", blank=True, null=True)
    city = models.CharField(max_length=255, help_text="City", verbose_name="City")
    state = models.CharField(max_length=255, help_text="State", verbose_name="State")
    country = models.CharField(max_length=255, help_text="Country", verbose_name="Country")
    zip_code = models.CharField(max_length=20, help_text="Zip Code", verbose_name="Zip Code")


class ClinicSettings(models.Model):
    name = models.CharField(max_length=255, help_text="Name of the clinic", verbose_name="Clinic Name")
    logo = models.ImageField(upload_to='clinic_logos/', help_text="Logo of the clinic", verbose_name="Clinic Logo")
    address = models.OneToOneField(Address, on_delete=models.CASCADE, help_text="Address of the clinic", verbose_name="Clinic Address")
    contact_email = models.EmailField(help_text="Contact email for the clinic", verbose_name="Contact Email")
    contact_number = models.CharField(max_length=20, help_text="Contact number for the clinic", verbose_name="Contact Number")

