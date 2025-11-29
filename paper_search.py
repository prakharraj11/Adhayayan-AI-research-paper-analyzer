# paper_search.py - Extract references and generate related papers
import re
from llm_agent import get_llm

def extract_references_from_text(pdf_text: str) -> list:
    """
    Extract references/bibliography from PDF text.
    """
    try:
        # Look for references section
        ref_patterns = [
            r'(?:references|bibliography|works cited)\s*\n(.*?)(?:\n\n\n|\Z)',
            r'(?:references|bibliography)\s*\n(.*?)(?:appendix|\Z)',
        ]
        
        references = []
        for pattern in ref_patterns:
            match = re.search(pattern, pdf_text.lower(), re.DOTALL | re.IGNORECASE)
            if match:
                ref_text = match.group(1)
                
                # Extract individual references
                ref_lines = re.findall(r'([A-Z][^.]+\.\s*\(\d{4}\)[^.]+\.)', ref_text)
                references.extend(ref_lines[:10])  # Limit to 10
                break
        
        return references
    except Exception as e:
        print(f"Error extracting references: {e}")
        return []

def generate_related_papers_with_llm(pdf_summaries: list, user_response: str) -> str:
    """
    Use LLM to generate related papers.
    """
    llm = get_llm()
    
    # Combine PDF summaries
    combined_summary = "\n".join([f"- {pdf['summary']}" for pdf in pdf_summaries[:3]])
    
    prompt = f"""You are an academic research assistant. Based on the following research papers, suggest 5 highly relevant academic papers.

UPLOADED PAPERS SUMMARY:
{combined_summary}

Generate 5 related papers in this EXACT format (use bullet points with •):

• **[Paper Title 1]** by Author1, Author2 et al. (2023)
  Research area and brief relevance explanation in one line.

• **[Paper Title 2]** by Author1, Author2 (2022)
  Research area and brief relevance explanation in one line.

REQUIREMENTS:
- Use bullet point (•) for each paper
- Make titles realistic and academic
- Years between 2019-2025
- Keep each description to ONE line only
- No extra formatting or sections

Generate exactly 5 papers with bullet points:"""

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        return f"Could not generate related papers: {str(e)}"

def search_papers_from_pdf(pdfs: list, response_text: str) -> str:
    """
    Main function to generate citations section.
    Combines extracted references and LLM-generated related papers.
    """
    html_output = ""
    
    # 1. Try to extract references from PDFs (using pdf_text from database)
    all_references = []
    for pdf in pdfs[:2]:  # Check first 2 PDFs
        pdf_text = pdf.get('pdf_text', '')
        if pdf_text:
            refs = extract_references_from_text(pdf_text)
            all_references.extend(refs)
    
    if all_references:
        html_output += "<p style='color: #a78bfa; font-weight: 600; margin: 0 0 10px 0;'>📚 References from Paper:</p>"
        html_output += "<ul style='margin: 0 0 15px 0; padding-left: 20px;'>"
        for i, ref in enumerate(all_references[:5], 1):  # Show max 5 references
            html_output += f"<li style='margin: 5px 0; color: #d1d5db;'>{ref}</li>"
        html_output += "</ul>"
    
    # 2. Generate related papers using LLM
    html_output += "<p style='color: #a78bfa; font-weight: 600; margin: 15px 0 10px 0;'>🔬 Related Research Papers:</p>"
    related_papers = generate_related_papers_with_llm(pdfs, response_text)
    html_output += f"<div style='color: #d1d5db; line-height: 1.8;'>{related_papers}</div>"
    
    return html_output
