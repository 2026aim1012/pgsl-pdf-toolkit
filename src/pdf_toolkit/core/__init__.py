"""
Core backend operations and registry for PGSL PDF Toolkit.
"""

from pdf_toolkit.core.numbering import (
    add_page_numbers,
    page_numbers,
)
from pdf_toolkit.core.operations import (
    apply_watermark,
    compress_pdf,
    delete_pages,
    export_text,
    images_to_pdf,
    merge_pdfs,
    ocr_document,
    pdf_to_images,
    reverse_pages,
    rotate_pages,
)
from pdf_toolkit.core.page_ops import (
    insert_pages,
    move_pages_order,
    reorder_pages,
)
from pdf_toolkit.core.registry import (
    OperationInfo,
    OperationKind,
    OperationsRegistry,
    default_registry,
    get_default_registry,
)

__all__ = [
    "OperationInfo",
    "OperationKind",
    "OperationsRegistry",
    "add_page_numbers",
    "apply_watermark",
    "compress_pdf",
    "default_registry",
    "delete_pages",
    "export_text",
    "get_default_registry",
    "images_to_pdf",
    "insert_pages",
    "merge_pdfs",
    "move_pages_order",
    "ocr_document",
    "page_numbers",
    "pdf_to_images",
    "reorder_pages",
    "reverse_pages",
    "rotate_pages",
]
