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