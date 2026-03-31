import base64
import os
from PIL import Image
import io
from .ai_service import LocalAIService

class ImageReportProcessor:
    """
    Service to handle Lab Report Images (JPG/PNG) using Vision LLMs.
    """
    def __init__(self, model_name="llama3.2-vision"):
        # Hum Vision model use karenge jo images samajhta hai
        self.ai = LocalAIService(model_name=model_name)

    def encode_image(self, image_path):
        """
        Image file ko Base64 string mein badalta hai Ollama ke liye.
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
        
    def process_image(self, image_path, report_name = "General"):
        """
        image upload hone par ai se data extract karta hai 
        """
        try:
            if not os.path.exists(image_path):
                return FileNotFoundError(f"Image not found at {image_path}")
            
            base64_image = self.encode_image(image_path)

            prompt = self.ai.get_prompt_by_type(report_name)

            response = self.ai.llm.invoke(
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        ],
                    }
                ]
            )

            return {
                "ok": True,
                "extracted_json": response.content
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e)
            }
        


            

