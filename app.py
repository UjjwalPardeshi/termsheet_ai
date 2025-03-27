import io
import filetype
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import pytesseract
from PIL import Image
import models
from database import SessionLocal, engine, Base
from pdf2image import convert_from_bytes

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/upload/")
async def upload_termsheet(file: UploadFile = File(...), db: Session = Depends(get_db)):
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
            ocr_result = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            extracted_text = " ".join(ocr_result["text"]).strip()
            confidence_score = sum(ocr_result["conf"]) / len(ocr_result["conf"]) if ocr_result["conf"] else 0.0

        # Process PDF Files
        elif file_type.mime == "application/pdf":
            images = convert_from_bytes(file_bytes)
            if not images:
                raise HTTPException(status_code=400, detail="Could not extract images from PDF")
            
            for img in images:
                ocr_result = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                extracted_text += " ".join(ocr_result["text"]).strip() + "\n"
                confidence_score += sum(ocr_result["conf"]) / len(ocr_result["conf"]) if ocr_result["conf"] else 0.0
            
            confidence_score /= max(len(images), 1)  # Avoid division by zero

        else:
            raise HTTPException(status_code=400, detail="Only images and PDFs are supported")

        # Store in Database
        new_termsheet = models.TermSheet(
            document_name=file.filename,
            document_type=file.content_type,
            extracted_text=extracted_text,
            ocr_confidence=confidence_score,  # Now valid
            validation_status="Pending"
        )
        db.add(new_termsheet)
        db.commit()
        db.refresh(new_termsheet)

        return {
            "filename": file.filename,
            "extracted_text": extracted_text,
            "ocr_confidence": confidence_score,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
