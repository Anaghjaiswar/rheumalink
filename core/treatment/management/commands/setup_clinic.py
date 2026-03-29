from django.core.management.base import BaseCommand
from patient.models import Comorbidity
from treatment.models import Medicine
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Seeds the database with initial comorbidities and rheumatology medicines'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Starting Clinic Setup ---'))

        # 1. Seed Comorbidities
        comorbidities_list = [
            "Diabetes Mellitus (Sugar)",
            "Hypertension (High BP)",
            "Dyslipidemia (High Cholesterol)",
            "Hypothyroidism",
            "Hyperthyroidism",
            "Osteoporosis (Weak Bones)",
            "Osteoarthritis",
            "Bronchial Asthma",
            "ILD (Interstitial Lung Disease)",
            "CAD (Heart Disease)",
            "CKD (Kidney Disease)",
            "Tuberculosis (TB)",
            "Hepatitis B/C",
            "Anemia",
            "Obesity",
            "PUD (Peptic Ulcer)"
        ]

        for name in comorbidities_list:
            obj, created = Comorbidity.objects.get_or_create(name=name)
            if created:
                self.stdout.write(f"Added Comorbidity: {name}")

        # 2. Seed Common Rheumatology Medicines
        # Format: (Name, Generic, Form, Strength, Category)
        medicines = [
            ('Methotrexate 7.5', 'Methotrexate', 'Tablet', '7.5mg', 'DMARD'),
            ('Methotrexate 10', 'Methotrexate', 'Tablet', '10mg', 'DMARD'),
            ('HCQ 200', 'Hydroxychloroquine', 'Tablet', '200mg', 'Antimalarial'),
            ('HCQ 400', 'Hydroxychloroquine', 'Tablet', '400mg', 'Antimalarial'),
            ('Sulfasalazine 500', 'Sulfasalazine', 'Tablet', '500mg', 'DMARD'),
            ('Leflunomide 10', 'Leflunomide', 'Tablet', '10mg', 'DMARD'),
            ('Leflunomide 20', 'Leflunomide', 'Tablet', '200mg', 'DMARD'),
            ('Folitrax 15', 'Methotrexate', 'Injection', '15mg', 'DMARD'),
            ('Prednisolone 5', 'Prednisolone', 'Tablet', '5mg', 'Steroid'),
            ('Prednisolone 10', 'Prednisolone', 'Tablet', '10mg', 'Steroid'),
            ('Etoricoxib 60', 'Etoricoxib', 'Tablet', '60mg', 'NSAID'),
            ('Naproxen 500', 'Naproxen', 'Tablet', '500mg', 'NSAID'),
            ('Tofacitinib 5', 'Tofacitinib', 'Tablet', '5mg', 'JAK Inhibitor'),
            ('Zyloric 100', 'Allopurinol', 'Tablet', '100mg', 'Anti-Gout'),
        ]

        for m_name, g_name, form, strength, cat in medicines:
            obj, created = Medicine.objects.get_or_create(
                medicine_name=m_name,
                defaults={
                    'generic_name': g_name,
                    'form': form,
                    'strength': strength,
                    'category': cat
                }
            )
            if created:
                self.stdout.write(f"Added Medicine: {m_name}")

        self.stdout.write(self.style.SUCCESS('--- Clinic Setup Complete ---'))