"""Text extraction and preprocessing utilities."""

import html2text
import requests
from typing import Optional
import io


def fetch_url(url: str) -> Optional[str]:
    """
    Fetch content from a URL.
    
    Args:
        url: URL to fetch
        
    Returns:
        Raw HTML content or None if fetch fails
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"✗ Failed to fetch URL {url}: {e}")
        return None


def extract_text_from_html(html_content: str) -> str:
    """
    Convert HTML to clean text.
    
    Args:
        html_content: Raw HTML content
        
    Returns:
        Clean text content
    """
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.ignore_emphasis = False
    return h.handle(html_content)


def extract_text_from_pdf(file_content: bytes) -> str:
    """
    Extract text from PDF file.
    
    Args:
        file_content: PDF file bytes
        
    Returns:
        Extracted text content
    """
    try:
        from pypdf import PdfReader
        pdf_file = io.BytesIO(file_content)
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


def extract_text_from_docx(file_content: bytes) -> str:
    """
    Extract text from DOCX file.
    
    Args:
        file_content: DOCX file bytes
        
    Returns:
        Extracted text content
    """
    try:
        from docx import Document
        docx_file = io.BytesIO(file_content)
        doc = Document(docx_file)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        raise ValueError(f"Failed to extract text from DOCX: {e}")


def extract_text_from_txt(file_content: bytes) -> str:
    """
    Extract text from plain text file.
    
    Args:
        file_content: Text file bytes
        
    Returns:
        Text content
    """
    try:
        # Try UTF-8 first
        return file_content.decode('utf-8')
    except UnicodeDecodeError:
        # Fallback to latin-1
        return file_content.decode('latin-1', errors='ignore')


def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """
    Extract text from various file types.
    
    Args:
        file_content: File bytes
        filename: Original filename
        
    Returns:
        Extracted text content
    """
    filename_lower = filename.lower()
    
    if filename_lower.endswith('.pdf'):
        return extract_text_from_pdf(file_content)
    elif filename_lower.endswith(('.docx', '.doc')):
        return extract_text_from_docx(file_content)
    elif filename_lower.endswith(('.txt', '.md', '.markdown')):
        return extract_text_from_txt(file_content)
    elif filename_lower.endswith(('.html', '.htm')):
        return extract_text_from_html(file_content.decode('utf-8'))
    else:
        # Try as plain text
        return extract_text_from_txt(file_content)


def preprocess_text(text: str) -> str:
    """
    Preprocess text for LLM extraction.
    
    Args:
        text: Raw text content
        
    Returns:
        Preprocessed text
    """
    # Remove excessive whitespace
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]  # Remove empty lines
    return '\n'.join(lines)

