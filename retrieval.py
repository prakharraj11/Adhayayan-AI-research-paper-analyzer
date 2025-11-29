# retrieval.py - Retrieve from PDF texts stored in database
from typing import List, Dict

def extract_chunks_from_text(pdf_text: str, filename: str) -> List[Dict]:
    """
    Split PDF text into chunks by pages.
    """
    chunks = []
    
    # Split by page markers
    pages = pdf_text.split("--- Page ")
    
    for page_text in pages:
        if not page_text.strip():
            continue
        
        # Extract page number
        try:
            page_num_end = page_text.find(" ---")
            if page_num_end > 0:
                page_num = page_text[:page_num_end].strip()
                text = page_text[page_num_end + 4:].strip()
            else:
                page_num = "1"
                text = page_text.strip()
        except:
            page_num = "?"
            text = page_text.strip()
        
        if text:
            chunks.append({
                "text": text,
                "page": page_num,
                "source": filename
            })
    
    return chunks

def simple_keyword_search(query: str, chunks: List[Dict], top_k: int = 5) -> List[Dict]:
    """
    Simple keyword-based search to find relevant chunks.
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())
    
    # Score each chunk based on keyword overlap
    scored_chunks = []
    for chunk in chunks:
        text_lower = chunk['text'].lower()
        text_words = set(text_lower.split())
        
        # Calculate overlap score
        overlap = len(query_words & text_words)
        
        # Bonus for exact phrase match
        if query_lower in text_lower:
            overlap += 10
        
        if overlap > 0:
            scored_chunks.append((overlap, chunk))
    
    # Sort by score and return top_k
    scored_chunks.sort(reverse=True, key=lambda x: x[0])
    return [chunk for _, chunk in scored_chunks[:top_k]]

def retrieve_from_pdf_texts(query: str, pdfs: List[Dict], top_k: int = 6) -> List[Dict]:
    """
    Retrieve relevant chunks from multiple PDFs stored in database.
    
    Args:
        query: User's question
        pdfs: List of PDF records from database (contains pdf_text field)
        top_k: Number of chunks to return
    
    Returns:
        List of relevant text chunks with metadata
    """
    all_chunks = []
    
    # Extract chunks from all PDFs
    for pdf in pdfs:
        if pdf.get('pdf_text'):
            chunks = extract_chunks_from_text(pdf['pdf_text'], pdf['filename'])
            all_chunks.extend(chunks)
    
    if not all_chunks:
        return [{
            "text": "No document content available.",
            "page": "0",
            "source": "System"
        }]
    
    # Retrieve most relevant chunks
    relevant_chunks = simple_keyword_search(query, all_chunks, top_k)
    
    # If no relevant chunks found, return first few chunks as fallback
    if not relevant_chunks:
        relevant_chunks = all_chunks[:top_k]
    
    return relevant_chunks
