# ingest.py - PDF ingestion (stores text in database, no file storage)
import os
from pypdf import PdfReader
from llm_agent import summarize_document
import io

def ingest_pdf_to_text(upload_file) -> tuple:
    """
    Process a PDF file and extract text (no file storage needed).
    
    Returns:
        (pdf_text, pages_count, summary, pdf_name)
    """
    pdf_name = os.path.splitext(upload_file.filename)[0]
    
    print(f"📄 Processing {pdf_name}...")
    
    try:
        # Read PDF directly from upload without saving to disk
        pdf_bytes = upload_file.file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        
        # Extract text from all pages
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages_text.append(f"--- Page {i+1} ---\n{text}")
        
        if not pages_text:
            raise ValueError(f"No text could be extracted from {pdf_name}")
        
        # Combine all pages into single text
        full_text = "\n\n".join(pages_text)
        pages_count = len(pages_text)
        
        print(f"✅ Extracted text from {pages_count} pages")
        
        # Generate summary
        print(f"🔄 Generating summary...")
        try:
            doc_summary = summarize_document(full_text)
            print(f"✅ Summary: {doc_summary[:100]}...")
        except Exception as e:
            print(f"❌ Error generating summary: {e}")
            doc_summary = f"Document: {pdf_name}. {pages_text[0][:300]}..."
        
        print(f"✅ Processed {pdf_name}: {pages_count} pages")
        
        return full_text, pages_count, doc_summary, pdf_name
        
    except Exception as e:
        print(f"❌ Error processing PDF: {e}")
        raise ValueError(f"Failed to process {pdf_name}: {str(e)}")
