import re
from typing import Iterable, List
from patient.models import PatientProfile

def extract_phone_number_from_user_id(user_id: int) -> str:
    try:
        patient_profile = PatientProfile.objects.get(user_id=user_id)
        return patient_profile.contact_no
    except PatientProfile.DoesNotExist:
        raise ValueError("Invalid user ID or patient profile not found." + f" User ID: {user_id}")
    

def extract_phone_from_jid(jid):
        """
        Parses '918077045850@s.whatsapp.net' -> '8077045850'
        Assumes Indian 10-digit standard.
        """
        if not jid:
            return None
        
        # Remove the suffix
        clean = jid.split('@')[0]
        
        # If it starts with 91 and is 12 digits, strip 91. 
        # Or simpler: just take the last 10 digits.
        if len(clean) >= 10:
            return clean[-10:] 
        
        return clean