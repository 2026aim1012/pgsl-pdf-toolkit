"""
Core backend operations and registry for PGSL PDF Toolkit.
"""

from pdf_toolkit.core.operations import (
    apply_watermark,
    compress_pdf,
    delete_pages,
    export_text,
    merge_pdfs,
    ocr_document,
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
    "apply_watermark",
    "compress_pdf",
    "default_registry",
    "delete_pages",
    "export_text",
    "get_default_registry",
    "insert_pages",
    "merge_pdfs",
    "move_pages_order",
    "ocr_document",
    "reorder_pages",
    "reverse_pages",
    "rotate_pages",
]
