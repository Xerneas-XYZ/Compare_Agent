import gc
import logging
import tempfile
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
from pypdf import PdfReader, PdfWriter
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

logger = logging.getLogger(__name__)

pipeline_options = PdfPipelineOptions()
pipeline_options.images_scale = 1.0
pipeline_options.do_table_structure = True
pipeline_options.do_ocr = False

doc_converter = DocumentConverter(
    allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)

@dataclass
class StructuralChunk:
    text: str
    section_title: str
    metadata: Dict[str, Any]

def parse_markdown_to_structural_chunks(markdown_text: str, doc_label: str) -> List[StructuralChunk]:
    """
    Implements Strategy Step 1: Ingestion Phase.
    Parses Markdown lines to track section headers and tag every chunk with its precise 
    location in the document hierarchy.
    """
    lines = markdown_text.splitlines()
    chunks = []
    current_section = "Introduction / Preamble"
    current_buffer = []
    buffer_tokens = 0
    
    # Simple token estimator (4 characters per token average)
    def estimate_tokens(text: str) -> int:
        return len(text) // 4

    heading_pattern = re.compile(r"^(#{1,4})\s+(.+)$")

    for line in lines:
        match = heading_pattern.match(line)
        if match:
            # If we have content in the buffer, flush it before switching sections
            if current_buffer:
                content = "\n".join(current_buffer)
                chunks.append(StructuralChunk(
                    text=content,
                    section_title=current_section,
                    metadata={"doc_label": doc_label, "section": current_section}
                ))
                current_buffer = []
                buffer_tokens = 0
            current_section = match.group(2).strip()
            
        current_buffer.append(line)
        buffer_tokens += estimate_tokens(line)
        
        # Split chunk if it exceeds our token window target (approx 600 tokens for clean alignment)
        if buffer_tokens >= 600:
            content = "\n".join(current_buffer)
            chunks.append(StructuralChunk(
                text=content,
                section_title=current_section,
                metadata={"doc_label": doc_label, "section": current_section}
            ))
            current_buffer = []
            buffer_tokens = 0

    if current_buffer:
        chunks.append(StructuralChunk(
            text="\n".join(current_buffer),
            section_title=current_section,
            metadata={"doc_label": doc_label, "section": current_section}
        ))

    return chunks

def chunk_isolated_ingest(file_path: Path, suffix: str, doc_label: str, block_size: int = 8) -> List[Dict[str, Any]]:
    """Converts documents to layout-aware structural chunk models."""
    if suffix == ".docx":
        raw_md = doc_converter.convert(file_path).document.export_to_markdown()
        struct_chunks = parse_markdown_to_structural_chunks(raw_md, doc_label)
        return [{"text": c.text, "metadata": c.metadata} for c in struct_chunks]

    reader = PdfReader(str(file_path))
    total_pages = len(reader.pages)
    raw_md_segments = []

    for base in range(0, total_pages, block_size):
        edge = min(base + block_size, total_pages)
        writer = PdfWriter()
        for idx in range(base, edge):
            writer.add_page(reader.pages[idx])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as slice_tmp:
            writer.write(slice_tmp.name)
            slice_path = Path(slice_tmp.name)

        try:
            raw_md_segments.append(doc_converter.convert(slice_path).document.export_to_markdown())
        finally:
            slice_path.unlink(missing_ok=True)
            del writer
            gc.collect()

    combined_md = "\n\n".join(raw_md_segments)
    struct_chunks = parse_markdown_to_structural_chunks(combined_md, doc_label)
    return [{"text": c.text, "metadata": c.metadata} for c in struct_chunks]