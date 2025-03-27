import io
import filetype
from fastapi import FastAPI, HTTPException, UploadFile, File
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
from database import db  # Import Firestore DB from database.py
from google.cloud import firestore  # Import Firestore
import spacy
import re

app = FastAPI()

# Load spaCy model for NER
nlp = spacy.load("en_core_web_sm")

# Define regex patterns for mandatory financial terms in a term sheet
regex_patterns = {
    "VALUATION": r"\b(pre-money valuation of \$?\d+(?:,\d{3})*|post-money valuation of \$?\d+(?:,\d{3})*)\b",
    "EQUITY_STAKE": r"\b(\d+% equity|equity of \d+%)\b",
    "SHAREHOLDING_STRUCTURE": r"\b(\d+ shares|issued share capital|fully diluted basis)\b",
    "VOTING_RIGHTS": r"\b(super voting rights|majority voting|preferred voting)\b",
    "LIQUIDATION_PREFERENCE": r"\b(liquidation preference of \d+x|participating liquidation)\b",
    "ANTI_DILUTION_PROTECTION": r"\b(weighted average|full ratchet|price adjustment)\b",
    "EXIT_TERMS": r"\b(exit strategy|buyout clause|liquidation event|initial public offering|IPO)\b",
    "DRAG_ALONG_RIGHTS": r"\b(drag-along rights|forced sale provision)\b",
    "TAG_ALONG_RIGHTS": r"\b(tag-along rights|co-sale agreement)\b",
    "BOARD_SEATS": r"\b(\d+ board seats|right to appoint \d+ directors)\b",
    "DIVIDENDS": r"\b(dividend yield|dividend payments|dividends per share)\b",
    "VESTING_SCHEDULE": r"\b(vesting over \d+ years|cliff period of \d+ months)\b",
    "LOCKUP_PERIOD": r"\b(lockup period of \d+ months|restricted sale period)\b",
    "CONVERTIBLE_NOTES": r"\b(convertible note at \$?\d+ valuation|convertible debt)\b",
    "LOAN_TERMS": r"\b(loan maturity|interest rate of \d+%)\b",
    "DISPUTE_RESOLUTION": r"\b(arbitration in \w+ jurisdiction|dispute resolution mechanism)\b",
    "CONFIDENTIALITY_CLAUSE": r"\b(non-disclosure agreement|confidentiality clause|confidential information)\b",
    "GOVERNING_LAW": r"\b(governed by the laws of [A-Za-z]+|jurisdiction in [A-Za-z]+)\b"
}

def extract_entities(text):
    """Extracts named entities and financial terms from the text."""
    doc = nlp(text)
    entities = {ent.label_: ent.text for ent in doc.ents}

    # Apply regex patterns
    for label, pattern in regex_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            entities[label] = match.group(0)

    return entities

def process_ocr(image: Image.Image):
    """Extract text & confidence from an image using Tesseract OCR."""
    ocr_result = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    
    extracted_text = " ".join(ocr_result["text"]).strip()
    confidence_scores = [conf for conf in ocr_result["conf"] if conf != "-1"]  # Remove invalid scores
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0

    return extracted_text, avg_confidence

@app.post("/upload/")
async def upload_termsheet(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        file_type = filetype.guess(file_bytes)
        
        if not file_type:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        extracted_text = ""
        confidence_score = 0.0

        # Process Image Files
        if file_type.mime.startswith("image"):
            image = Image.open(io.BytesIO(file_bytes))
            extracted_text, confidence_score = process_ocr(image)

        # Process PDF Files
        elif file_type.mime == "application/pdf":
            images = convert_from_bytes(file_bytes)
            if not images:
                raise HTTPException(status_code=400, detail="Could not extract images from PDF")
            
            for img in images:
                text, conf = process_ocr(img)
                extracted_text += text + "\n"
                confidence_score += conf
            
            confidence_score /= max(len(images), 1)  # Avoid division by zero

        else:
            raise HTTPException(status_code=400, detail="Only images and PDFs are supported")

        # Extract named entities
        entities = extract_entities(extracted_text)

        # Store in Firestore
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
