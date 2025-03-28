from fastapi import FastAPI, HTTPException, UploadFile, File
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
import spacy
import re
import os
import io
import filetype
import imaplib
import email
import pandas as pd
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

app = FastAPI()

load_dotenv()

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Email credentials
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

if not EMAIL_USER or not EMAIL_PASSWORD:
    raise RuntimeError("Set EMAIL_USER and EMAIL_PASSWORD as environment variables.")

IMAP_SERVER = "imap.gmail.com"

# Firebase initialization
cred = credentials.Certificate("/var/home/ujjain/Desktop/code/termsheet_ai/termsheetai-firebase-adminsdk-fbsvc-a9cc2706a1.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Financial terms regex
regex_patterns = {
    "VALUATION": r"\b(pre-money valuation of \$?\d+(?:,\d{3})*|post-money valuation of \$?\d+(?:,\d{3})*)\b",
    "EQUITY_STAKE": r"\b(\d+% equity|equity of \d+%)\b",
    "EXIT_TERMS": r"\b(exit strategy|buyout clause|IPO)\b",
    "GOVERNING_LAW": r"\b(governed by the laws of [A-Za-z]+|jurisdiction in [A-Za-z]+)\b",
}

def extract_entities(text):
    """Extract named entities and financial terms."""
    doc = nlp(text)
    entities = {ent.label_: ent.text for ent in doc.ents}
    
    for label, pattern in regex_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            entities[label] = match.group(0)

    return entities

def process_ocr(image: Image.Image):
    """Perform OCR on an image."""
    ocr_result = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    extracted_text = " ".join(ocr_result["text"]).strip()
    confidence_scores = [int(conf) for conf in ocr_result["conf"] if str(conf).isdigit()]
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    return extracted_text, avg_confidence

@app.post("/upload/")
async def upload_termsheet(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        file_type = filetype.guess(file_bytes)

        if not file_type or not file_type.mime:
            raise HTTPException(status_code=400, detail="Unsupported or unknown file type")

        extracted_text = ""
        confidence_score = 0.0

        if file_type.mime.startswith("image"):
            image = Image.open(io.BytesIO(file_bytes))
            extracted_text, confidence_score = process_ocr(image)

        elif file_type.mime == "application/pdf":
            images = convert_from_bytes(file_bytes)
            if not images:
                raise HTTPException(status_code=400, detail="Could not extract images from PDF")
            for img in images:
                text, conf = process_ocr(img)
                extracted_text += text + "\n"
                confidence_score += conf
            confidence_score /= max(len(images), 1)
        
        elif file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
            extracted_text = df.to_string()
        
        elif file.filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_bytes))
            extracted_text = df.to_string()

        else:
            raise HTTPException(status_code=400, detail="Only images, PDFs, CSVs, and Excel files are supported")

        entities = extract_entities(extracted_text)

        # Save to Firestore
        doc_ref = db.collection("termsheets").document()
        doc_ref.set({
            "document_name": file.filename,
            "document_type": file.content_type,
            "extracted_text": extracted_text,
            "ocr_confidence": confidence_score,
            "entities": entities,
            "validation_status": "Pending",
            "created_at": firestore.SERVER_TIMESTAMP
        })

        return {
            "message": "File uploaded successfully",
            "document_id": doc_ref.id,
            "ocr_confidence": confidence_score,
            "extracted_entities": entities
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fetch-emails/")
async def fetch_emails():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_USER, EMAIL_PASSWORD)
        mail.select("inbox")

        result, data = mail.search(None, '(SUBJECT "Term Sheet")')
        email_ids = data[0].split()
        extracted_emails = []

        for email_id in email_ids[-5:]:
            result, msg_data = mail.fetch(email_id, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            email_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        email_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break

            entities = extract_entities(email_text)

            doc_ref = db.collection("emails").document()
            doc_ref.set({
                "subject": msg["subject"],
                "from": msg["from"],
                "body": email_text,
                "entities": entities,
                "created_at": firestore.SERVER_TIMESTAMP
            })

            extracted_emails.append({
                "subject": msg["subject"],
                "from": msg["from"],
                "body": email_text,
                "extracted_entities": entities
            })

        mail.logout()
        return {"emails": extracted_emails}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
