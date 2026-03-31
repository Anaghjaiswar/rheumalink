import os
import json
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

class LocalAIService:
    """
    Ollama (Local LLM) service with Dynamic Prompting based on report type.
    """
    
    def __init__(self, model_name="llama3"):
        ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        self.llm = ChatOllama(
            model=model_name,
            base_url=ollama_host,
            temperature=0 # this means no random guessing 
        )

    def get_prompt_by_type(self, report_name):
        """
        Report ke naam ke hisaab se specific prompt select karenge
        """
        report_name = report_name.upper()
        
        # Default Prompt
        prompt = "Extract all numerical values and units into a JSON format."

        if "CBC" in report_name:
            prompt = (
                "You are a hematology expert. Extract Hemoglobin, WBC Count, and Platelet Count. "
                "Format: {'Hemoglobin': {'value': 12, 'unit': 'g/dL'}, ...}"
            )
        elif "ESR" in report_name or "CRP" in report_name:
            prompt = (
                "Extract ESR (mm/hr) and CRP (mg/L) values for DAS28 calculation. "
                "Format: {'ESR': {'value': 20, 'unit': 'mm/hr'}, 'CRP': {'value': 5, 'unit': 'mg/L'}}"
            )
        elif "LIVER" in report_name or "LFT" in report_name:
            prompt = (
                "Extract SGOT (AST), SGPT (ALT), and Bilirubin. These are critical for Methotrexate monitoring. "
                "Format: {'SGPT': {'value': 35, 'unit': 'U/L'}, ...}"
            )
        elif "KIDNEY" in report_name or "KFT" in report_name or "CREATININE" in report_name:
            prompt = "Extract Serum Creatinine and Uric Acid. Format: {'Creatinine': {'value': 0.9, 'unit': 'mg/dL'}}"

        return prompt + " Return ONLY strictly valid JSON. If not found, use null."
    
    def extract_lab_data(self, report_text, report_name="General"):
        """
        Dynamic prompt ke saath data extract karta hai.
        """
        system_prompt = self.get_prompt_by_type(report_name)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Analyze this lab report text: {report_text}")
        ]
        
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return json.dumps({"error": f"Connection Error: {str(e)}"})
        
    def check_health(self):
        try:
            self.llm.invoke([HumanMessage(content="test")])
            return "Ready"
        except:
            return "Offline"