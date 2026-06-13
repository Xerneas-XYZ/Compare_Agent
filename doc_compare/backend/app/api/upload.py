import uuid
import logging
import tempfile
import gc  # 🌟 Added to forcefully free up RAM between chunks
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.concurrency import run_in_threadpool

from pypdf import PdfReader, PdfWriter

# Docling Core & CPU Configuration Imports
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice

from app.core.config import settings
from app.api.compare import store_doc

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024

# 1. Initialize Pipeline Options targeting local CPU cores
pipeline_options = PdfPipelineOptions()


# Optimize resolution scales to further mitigate RAM footprints on massive files
pipeline_options.images_scale = 1.0  

# Keep high-fidelity table extraction active
pipeline_options.do_table_structure = True 
pipeline_options.do_ocr = False  

# 2. Bind pipeline configurations to the PDF processing module
pdf_format_options = PdfFormatOption(pipeline_options=pipeline_options)

# 3. Instantiate the converter globally
doc_converter = DocumentConverter(
    allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
    format_options={InputFormat.PDF: pdf_format_options}
)

def extract_with_sequential_chunks(file_path: str, ext: str, chunk_size: int = 8):
    """
    Parses documents in tiny page slices (default: 8 pages) to ensure 
    the system never throws an out-of-memory std::bad_alloc exception.
    """
    if ext == ".docx":
        conv_result = doc_converter.convert(file_path)
        return conv_result.document.export_to_markdown(), 1

    reader = PdfReader(file_path)
    total_pages = len(reader.pages)
    
    # If the PDF is small, parse it directly in one pass
    if total_pages <= chunk_size:
        conv_result = doc_converter.convert(file_path)
        return conv_result.document.export_to_markdown(), total_pages

    logger.info(f"Dense PDF detected ({total_pages} pages). Slicing into safe segments of {chunk_size}...")
    combined_markdown = []

    # Iterate through the document in ultra-small segments
    for start_page in range(0, total_pages, chunk_size):
        end_page = min(start_page + chunk_size, total_pages)
        logger.info(f"Extracting layout range safely: pages {start_page} to {end_page}")

        writer = PdfWriter()
        for page_num in range(start_page, end_page):
            writer.add_page(reader.pages[page_num])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as split_tmp:
            writer.write(split_tmp.name)
            split_path = split_tmp.name

        try:
            conv_result = doc_converter.convert(split_path)
            combined_markdown.append(conv_result.document.export_to_markdown())
        finally:
            # Clean up the file path instantly
            Path(split_path).unlink(missing_ok=True)
            
            # 🌟 CRUCIAL: Force clear internal variables and free underlying C++ RAM allocations
            del writer
            gc.collect()

    return "\n\n".join(combined_markdown), total_pages


@router.post("/upload", summary="Upload a document for comparison")
async def upload_document(file: UploadFile = File(...)):
    logger.info(f"Processing single-threaded sequential layout extraction for file: {file.filename}")  
    
    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".pdf", ".docx"]:
        raise HTTPException(400, f"Unsupported format: {ext}. System optimized for PDF and DOCX only.")

    if file.size and file.size > MAX_BYTES:
        raise HTTPException(413, "File exceeds maximum allowed size thresholds.")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            # 🌟 Set the safe fallback chunk_size explicitly to 8 pages per run
            text, page_count = await run_in_threadpool(extract_with_sequential_chunks, temp_path, ext, 8)
        finally:
            Path(temp_path).unlink(missing_ok=True) 

        if not text.strip():
            raise HTTPException(422, "Unable to extract meaningful structured layout matrices.")

        doc_id = str(uuid.uuid4())
        
        clean_text = str(text)
        clean_filename = str(file.filename)
        clean_format = str(ext.replace(".", "")).strip().lower()
        clean_page_count = int(page_count)

        store_doc(doc_id, {
            "doc_id": doc_id,
            "filename": clean_filename,
            "text": clean_text,
            "metadata": {"format": clean_format},
            "page_count": clean_page_count,
            "char_count": len(clean_text),
        })

        return {
            "doc_id": doc_id,
            "filename": clean_filename,
            "char_count": len(clean_text),
            "page_count": clean_page_count,
            "format": clean_format,
        }

    except Exception as e:
        logger.exception("Docling Core Runtime Pipeline Breakdown:")
        raise HTTPException(500, f"Error converting document structures via single-thread runner: {str(e)}")
    finally:
        print("Final cleanup: Closing file and forcing garbage collection to free RAM.")
        await file.close()
        gc.collect()