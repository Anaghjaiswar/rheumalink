import math
from .models import Appointment, LabResult, Vitals, jointspain

class RheumaAnalyticsService:
    """
    Service class to handle complex Rheumatology calculations.
    Keeps models thin and logic centralized.
    """

    @staticmethod
    def calculate_das28_score(appointment_id):
        """
        Orchestrates data from Vitals, LabResults, and JointPain 
        to calculate the final DAS28 score for an appointment.
        """
        try:
            appointment = Appointment.objects.get(id=appointment_id)
            
            # 1. Get Joint Counts
            joint_chart = jointspain.objects.filter(patient_link=appointment.patient).latest('date_of_assessment')
            counts = RheumaAnalyticsService._get_joint_counts(joint_chart)
            
            # 2. Get Latest Lab Markers (ESR/CRP)
            # Fetching from the flexible JSON field we designed
            lab_report = LabResult.objects.filter(appointment=appointment).first()
            if not lab_report:
                # Fallback to the latest verified lab report of the patient
                lab_report = LabResult.objects.filter(patient=appointment.patient, is_verified=True).order_by('-test_date', '-created_at').first()
                
            esr = lab_report.get_marker_value('ESR') if lab_report else None
            crp = lab_report.get_marker_value('CRP') if lab_report else None
            
            # 3. Get Patient Global Health (GH) from Vitals or default to 50
            vitals = Vitals.objects.filter(appointment=appointment).first()
            gh = float(vitals.pain_scale) if vitals and getattr(vitals, 'pain_scale', None) is not None else 50.0

            # Calculation Logic
            tjc = counts['tender']
            sjc = counts['swollen']
            
            if esr:
                # DAS28-ESR Formula
                score = (0.56 * math.sqrt(tjc) + 0.28 * math.sqrt(sjc) + 
                         0.70 * math.log(esr) + 0.014 * gh)
                return {"score": round(score, 2), "type": "ESR"}
            
            elif crp:
                # DAS28-CRP Formula
                score = (0.56 * math.sqrt(tjc) + 0.28 * math.sqrt(sjc) + 
                         0.36 * math.log(crp + 1) + 0.014 * gh + 0.96)
                return {"score": round(score, 2), "type": "CRP"}
            
            return {"error": "Missing Lab Markers (ESR/CRP)"}

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _get_joint_counts(joint_chart):
        """Internal helper to count 28 specific joints."""
        das28_names = ['shoulder', 'elbow', 'wrist', 'knee']
        # Hand joints MCP 1-5, PIP 1-5
        for i in range(1, 6):
            das28_names.append(f'mcp{i}')
            das28_names.append(f'pip{i}')

        swollen = 0
        tender = 0

        # Logic to iterate through fields and count
        for field in joint_chart._meta.fields:
            name = field.name
            # Check if field is in DAS28 list (handling right/left suffixes)
            if any(base in name for base in das28_names) and ('right' in name or 'left' in name):
                val = getattr(joint_chart, name)
                if val == 'red': swollen += 1
                elif val == 'blue': tender += 1
                elif val == 'orange':
                    swollen += 1
                    tender += 1
        
        return {'swollen': swollen, 'tender': tender}