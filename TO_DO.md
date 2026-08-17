1. need to make celery background task so to whenever a lab report is uplaoded, 
pdf service will process that lab report and send it to ai service so that we 
can get structured data from that lab report and save it to database.

2. need to inclulcate logic of image extraction in pdf_service also becuase user can uplaod image also of the pdf report and we need to extract data from that image as well.

3. after the data is saved then we can do the calcualtion needed to be done on that data and then we can show the result to the user in the frontend. eg: calculating das28 score from the lab report data and then showing it to the user in the frontend.



                                                                                                    
  ### 2. Auto-Extract Appointments from WhatsApp Texts                                                           
                                                                                                                 
  Since you already have a WhatsApp webhook active, patients will send texts like "Hi, I want to book an         
  appointment with Dr. Mehta for tomorrow at 11 AM".                                                             
                                                                                                                 
  • The Flow: Instead of the compounder reading WhatsApp and typing the details manually into the Booking form,  
  the system parses the incoming text.                                                                           
  • The Feature: It places a "Pending Bookings from WhatsApp" section on the dashboard. The date, time, patient  
  profile, and doctor are already extracted. The compounder just reviews it and clicks "Approve" to create the   
  appointment in 1 click.                                                                                        
  • Cost: Low to $0. We can use a lightweight pattern-matching script or a basic, low-cost local parser rather   
  than calling heavy LLM models.                                                                                 
  ──────                                                                                                         
  ### 3. Patient ID/Card Camera Scanning (OCR)                                                                   
                                                                                                                 
  When a new patient arrives, typing their name, email, contact info, and date of birth manually takes 2–3       
  minutes.                                                                                                       
                                                                                                                 
  • The Flow: Add a "Scan ID Card" button. The compounder uses their phone or computer webcam to take a quick    
  picture of the patient's ID/Aadhaar/insurance card.                                                            
  • The Feature: A client-side JavaScript OCR library (like  Tesseract.js ) extracts the text and auto-populates 
  the registration form fields (First Name, Last Name, DOB, etc.).                                               
  • Cost: $0 (100% Free) because the image processing happens entirely inside the user's browser.                
  ──────                                                                                                         
  ### 4. Interactive HAQ Score Clicker                                                                           
                                                                                                                 
  The planning PDF mentions that the compounder needs to enter the Health Assessment Questionnaire (HAQ) score   
  during triage. Currently, they have to manually calculate this score.                                          
                                                                                                                 
  • The Feature: Instead of typing a number, we can add a quick interactive questionnaire modal. The compounder  
  asks the patient 8 quick questions (e.g., "Can you dress yourself?", "Can you climb stairs?") and clicks the   
  corresponding difficulty buttons (0 to 3). The system calculates the HAQ score automatically in real-time.     
  • Cost: $0 (simple client-side math).                         









  ### Summary of Missing APIs in Frontend (api.ts)                                           
                                                                                             
   Feature / Action in… │ Backend Endpoint     │ Status in Frontend … │ Impact
  ──────────────────────┼──────────────────────┼──────────────────────┼──────────────────────
   1. Medicine Auto-    │ GET                  │ ❌ Missing           │ Doctor has to type
   Suggest              │ /api/v1/autosuggest/ │                      │ medicine names
                        │ medicine/?q=         │                      │ manually without
                        │                      │                      │ autocomplete/strengt
                        │                      │                      │ h hints.
   2. Lab Test Auto-    │ GET                  │ ❌ Missing           │ Only predefined
   Suggest              │ /api/v1/autosuggest/ │                      │ common tests show;
                        │ labtest/?q=          │                      │ cannot search & add
                        │                      │                      │ custom lab tests
                         │                       │                   │ badges.
   3. Real-Time DAS28   │ GET                  │ ❌ Missing           │ Frontend hardcodes
   Score Calculator     │ /api/v1/das28/<appoi │                      │ "4.2" instead of
                        │ ntment_id>/          │                      │ calculating based on
                        │                      │                      │ joints + lab
   4. Diagnosis Status & │ GET /api/diagnosis-   │ ❌ Missing        │ Cannot check if Joint
   Completion Badges     │ status/<appointment_i │                   │ Chart or Rheumat
                         │ d>/                   │                   │ Checklist are
                         │                       │                   │ completed (✅
                         │                        │                 │ Filled).
   5. MedASR Voice       │ POST /api/proxy-       │ ❌ Missing      │ Medical voice
   Dictation: Spelling & │ correct-transcription/ │                 │ dictation does not
   Polish                │                        │                 │ polish transcriptions
   Polish                │ transcription/        │                   │ polish transcriptions
                         │                       │                   │ through AI service.
   6. MedASR Voice       │ POST /api/proxy-      │ ❌ Missing        │ Cannot auto-extract
   Dictation: Clinical   │ structure-clinical-   │                   │ complaints, findings,
   Structuring           │ note/                 │                   │ diagnosis, medicines
                         │                       │                   │ & tests from voice
                         │                       │                   │ note into form
                          │ id>/pdf/               │               │ backend Gotenberg
                          │                        │               │ engine is missing.
   8. Send Prescription   │ POST                   │ ❌ Missing    │ Direct WhatsApp
   via WhatsApp           │ /api/v1/prescription/< │               │ delivery of
                          │ id>/send/              │               │ prescription PDF to
                          │                        │               │ patient is not
                          │                        │               │ callable.
   9. Doctor              │ GET                    │ ❌ Missing    │ Notification popover in
   Notifications (Bell &  │ /notifications/api/lis │               │ top navigation cannot
   Unread Badges)         │ t/?role=DOCTOR         │               │ fetch doctor alerts.
   10. Mark Notification  │ POST                   │ ❌ Missing    │ Doctor cannot
   As Read                │ /notifications/api/<id │               │ dismiss/mark
                          │ >/read/                │               │ notifications read.
   11. Live Queue Polling │ GET                    │ ❌ Missing    │ Queue count cards
   / WebSocket Stats      │ /api/queue/?doctor=<id │               │ (Waiting, Attending,
                          │ >                      │               │ Attended) do not update
                          │                        │               │ in real-time.