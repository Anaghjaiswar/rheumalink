from storages.backends.s3 import S3Storage

class BaseMinioStorage(S3Storage):
    def url(self, name, parameters=None, expire=None, http_method=None):
        url = super().url(name, parameters, expire, http_method)
        # Swap Docker internal hostname with localhost for host browser access
        if url:
            url = url.replace('http://rheuma-minio:7000', 'http://127.0.0.1:7000')
        return url

class ClinicLogoStorage(BaseMinioStorage):
    bucket_name = 'clinic-logos'

class LabReportStorage(BaseMinioStorage):
    bucket_name = 'lab-reports'

class PrescriptionStorage(BaseMinioStorage):
    bucket_name = 'prescriptions'

class PatientDocumentStorage(BaseMinioStorage):
    bucket_name = 'patient-documents'
