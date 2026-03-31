import os
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .ai_service import LocalAIService
from logging import getLogger

all_logs = getLogger("all_logs.log")


class LabReportProcessor:
    """
    Service to handle PDF extraction and AI processing.
    """
    def __init__(self):
        self.ai = LocalAIService()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size = 1500,
            chunk_overlap = 200,
            seperators = ["\n\n", "\n", " ", ""]
        )

    def process_pdf(self, file_path):
        """
        workflow: Load pdf -> split -> AI extract
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            loader = PyMuPDFLoader(file_path)
            docs = loader.load()
            
            full_text = "\n".join([doc.page_content for doc in docs])
            chunks = self.splitter.split_text(full_text)

            raw_ai_response = self.ai.extract_lab_data(chunks[0])

            return {
                "ok": True,
                "message": "PDF processed successfully",
                "raw_text": full_text[:2000],
                "extracted_json": raw_ai_response
            }
        except Exception as e:
            all_logs.error(f"Error processing PDF: {e}")
            return {"ok": False, "error": str(e)}