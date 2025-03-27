
## **README - Term Sheet Extraction API**

### **Functionalities:**

1. **File Upload Endpoint (`/upload/`)**:
   - **Purpose**: Allows users to upload term sheet documents (images or PDFs) for OCR-based text extraction.
   - **Process**:
     - Accepts file uploads (supports images and PDFs).
     - Performs Optical Character Recognition (OCR) on the uploaded file.
     - Extracts and processes text for financial terms (e.g., valuation, equity stake, exit terms).
     - Calculates OCR confidence score based on extracted text.
     - Extracts named entities and financial terms using a pre-defined set of regex patterns.
     - Stores extracted text, OCR confidence score, and entities in Firebase Firestore.
   - **Response**:
     - Success message with the document ID, OCR confidence score, and extracted entities.

2. **Fetch Emails Endpoint (`/fetch-emails/`)**:
   - **Purpose**: Fetches emails from a Gmail inbox that have the subject "Term Sheet".
   - **Process**:
     - Connects to Gmail using IMAP with user credentials.
     - Filters emails with the subject "Term Sheet".
     - Extracts email body text (plain text format).
     - Extracts named entities and financial terms from the email body.
     - Stores email details (subject, sender, body, extracted entities) in Firebase Firestore.
   - **Response**:
     - List of extracted emails including subject, sender, body, and extracted entities.

### **Setup Instructions:**
1. **Install Dependencies**:
   - Install the necessary Python packages:
     ```bash
     pip install fastapi uvicorn pytesseract Pillow pdf2image spacy filetype firebase-admin python-dotenv imaplib email
     ```
   
2. **Environment Variables**:
   - Set `EMAIL_USER` and `EMAIL_PASSWORD` in a `.env` file for Gmail IMAP access.
   - Provide the path to the Firebase Admin SDK JSON key in the `credentials.Certificate()` function.
   
3. **Start the API Server**:
   - Run the FastAPI server:
     ```bash
     uvicorn app:app --reload
     ```

### **Notes**:
- Ensure Tesseract OCR and necessary dependencies are installed on the system for OCR processing.
- The `/upload/` endpoint processes both images and PDFs, extracting text and calculating OCR confidence.
- The `/fetch-emails/` endpoint only fetches emails with the subject "Term Sheet" and extracts relevant financial data.

