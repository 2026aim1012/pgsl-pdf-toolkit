"""
Unit tests for OperationsRegistry in pdf_toolkit.core.registry.
"""

from pathlib import Path
from typing import Any

import pytest

from pdf_toolkit.core.registry import (
    OperationInfo,
    OperationsRegistry,
    default_registry,
    get_default_registry,
)


def dummy_modifying_op(src: Path, out: Path, reporter: Any = None, **kwargs: Any) -> None:
    """A dummy modifying operation."""


def dummy_readonly_op(reporter: Any = None, src_path: Path | None = None, **kwargs: Any) -> str:
    """A dummy read-only operation."""
    return f"content of {src_path}"


def test_registry_initialization():
    reg = OperationsRegistry()
    assert len(reg) == 0
    assert list(reg.keys()) == []
    assert list(reg) == []


def test_registry_register_method():
    reg = OperationsRegistry()
    reg.register(
        "dummy_mod",
        dummy_modifying_op,
        kind="modifying",
        display_name="Dummy Mod",
        description="Does dummy modification",
    )

    assert "dummy_mod" in reg
    assert len(reg) == 1
    assert reg["dummy_mod"] is dummy_modifying_op
    assert reg.get("dummy_mod") is dummy_modifying_op

    info = reg.get_info("dummy_mod")
    assert isinstance(info, OperationInfo)
    assert info.name == "dummy_mod"
    assert info.kind == "modifying"
    assert info.is_modifying
    assert not info.is_read_only
    assert info.display_name == "Dummy Mod"
    assert info.description == "Does dummy modification"


def test_registry_register_decorator():
    reg = OperationsRegistry()

    @reg.register("decorated_op", kind="read_only", display_name="Decorated Op")
    def my_op(reporter=None, src_path=None):
        return "result"

    assert "decorated_op" in reg
    assert reg["decorated_op"] is my_op
    info = reg.get_info("decorated_op")
    assert info.is_read_only
    assert info.display_name == "Decorated Op"


def test_registry_invalid_kind():
    reg = OperationsRegistry()
    with pytest.raises(ValueError, match="kind must be 'modifying' or 'read_only'"):
        reg.register("bad", dummy_modifying_op, kind="invalid_kind")  # type: ignore


def test_registry_dict_interface():
    reg = OperationsRegistry()
    reg["custom"] = dummy_modifying_op

    assert "custom" in reg
    assert reg["custom"] is dummy_modifying_op
    assert reg.get("non_existent") is None
    assert reg.get("non_existent", "default") == "default"

    with pytest.raises(KeyError):
        _ = reg["non_existent"]

    assert list(reg.keys()) == ["custom"]
    assert list(reg.values()) == [dummy_modifying_op]
    assert list(reg.items()) == [("custom", dummy_modifying_op)]


def test_registry_unregister():
    reg = OperationsRegistry()
    reg.register("op1", dummy_modifying_op)
    assert "op1" in reg

    removed = reg.unregister("op1")
    assert removed is not None
    assert removed.name == "op1"
    assert "op1" not in reg
    assert len(reg) == 0

    assert reg.unregister("op1") is None


def test_registry_list_operations_filtering():
    reg = OperationsRegistry()
    reg.register("mod1", dummy_modifying_op, kind="modifying")
    reg.register("mod2", dummy_modifying_op, kind="modifying")
    reg.register("ro1", dummy_readonly_op, kind="read_only")

    assert len(reg.list_operations()) == 3
    mod_ops = reg.list_operations(kind="modifying")
    ro_ops = reg.list_operations(kind="read_only")

    assert [op.name for op in mod_ops] == ["mod1", "mod2"]
    assert [op.name for op in ro_ops] == ["ro1"]


def test_registry_to_dict():
    reg = OperationsRegistry()
    reg.register("mod", dummy_modifying_op)
    reg.register("read", dummy_readonly_op, kind="read_only")

    d = reg.to_dict()
    assert d == {"mod": dummy_modifying_op, "read": dummy_readonly_op}


def test_registry_bind_session():
    class FakeSession:
        current = Path("/tmp/active_document.pdf")

    session = FakeSession()
    reg = OperationsRegistry()
    reg.register("mod", dummy_modifying_op, kind="modifying")
    reg.register("read", dummy_readonly_op, kind="read_only")

    bound = reg.bind_session(session)
    assert callable(bound["mod"])
    assert callable(bound["read"])

    # Modifying op is unbound
    assert bound["mod"] is dummy_modifying_op

    # Read-only op injects session.current when src_path not provided
    result = bound["read"](reporter=None)
    assert result == "content of /tmp/active_document.pdf"

    # Explicit src_path is respected
    result_explicit = bound["read"](reporter=None, src_path=Path("/custom/path.pdf"))
    assert result_explicit == "content of /custom/path.pdf"


def test_default_registry_contents():
    reg = get_default_registry()
    expected_operations = {
        "rotate",
        "reverse",
        "delete",
        "merge",
        "watermark",
        "reorder",
        "insert",
        "compress",
        "export_text",
        "ocr",
    }
    for op_name in expected_operations:
        assert op_name in reg, f"Expected {op_name} to be in default registry"
        assert callable(reg[op_name])

    assert reg.get_info("rotate").is_modifying
    assert reg.get_info("export_text").is_read_only
    assert reg.get_info("ocr").is_read_only
    assert reg.get_info("reorder").is_modifying
    assert reg.get_info("insert").is_modifying
    assert reg.get_info("compress").is_modifying
    assert reg.get_info("watermark").is_modifying


def test_global_default_registry_singleton():
    assert isinstance(default_registry, OperationsRegistry)
    assert "rotate" in default_registry
    assert "reorder" in default_registry
