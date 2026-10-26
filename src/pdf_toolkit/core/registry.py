"""
registry.py: Operations Registry for PGSL PDF Toolkit.

Maintains a catalog of available backend operations (both modifying and read-only)
that can be invoked by the GUI panels (Toolkit, Explorer, Preview) via the Session hub.

Backend Contract:
-----------------
Modifying:
    op(src: Path, out: Path, reporter: Reporter | None, **opts) -> None
    - Reads from `src`, writes resulting document to `out`.
    - Must never modify `src` directly.
    - Can report progress with `reporter(done, total, msg)`.

Read-only:
    fn(reporter: Reporter | None, src_path: Path | None = None, **kwargs) -> Any
    - Inspects the document or extracts information (e.g. OCR, text extraction).
    - Returns data for the caller.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, KeysView
from dataclasses import dataclass
from typing import Any, Literal

OperationKind = Literal["modifying", "read_only"]


@dataclass(frozen=True)
class OperationInfo:
    """Metadata describing a registered PDF operation."""

    name: str
    func: Callable[..., Any]
    kind: OperationKind = "modifying"
    display_name: str = ""
    description: str = ""

    @property
    def is_modifying(self) -> bool:
        return self.kind == "modifying"

    @property
    def is_read_only(self) -> bool:
        return self.kind == "read_only"


class OperationsRegistry:
    """
    Central registry for PDF operations in PGSL PDF Toolkit.

    Provides dictionary-like access (`registry["rotate"]`), metadata inspection,
    decorator-based registration, and session-binding helpers for GUI integration.
    """

    def __init__(self) -> None:
        self._operations: dict[str, OperationInfo] = {}

    def register(
        self,
        name: str | None = None,
        func: Callable[..., Any] | None = None,
        *,
        kind: OperationKind = "modifying",
        display_name: str = "",
        description: str = "",
    ) -> Callable[..., Any]:
        """
        Register an operation. Can be used as a decorator or direct method.

        Usage as decorator:
            @registry.register("rotate", kind="modifying", display_name="Rotate Pages")
            def rotate(src, out, reporter, angle=90): ...

        Usage as method:
            registry.register("rotate", rotate_fn, kind="modifying")
        """
        if kind not in ("modifying", "read_only"):
            raise ValueError(f"kind must be 'modifying' or 'read_only', got {kind!r}")

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            op_name = name or fn.__name__
            info = OperationInfo(
                name=op_name,
                func=fn,
                kind=kind,
                display_name=display_name or op_name.replace("_", " ").title(),
                description=description or (fn.__doc__ or "").strip(),
            )
            self._operations[op_name] = info
            return fn

        if func is not None:
            return decorator(func)
        return decorator

    def unregister(self, name: str) -> OperationInfo | None:
        """Remove an operation from the registry by name."""
        return self._operations.pop(name, None)

    def get(self, name: str, default: Any = None) -> Callable[..., Any] | None:
        """Return the callable for the named operation, or default."""
        info = self._operations.get(name)
        return info.func if info is not None else default

    def get_info(self, name: str) -> OperationInfo | None:
        """Return metadata for the named operation, or None."""
        return self._operations.get(name)

    def list_operations(self, kind: OperationKind | None = None) -> list[OperationInfo]:
        """Return list of all registered operations, optionally filtered by kind."""
        if kind is None:
            return list(self._operations.values())
        return [op for op in self._operations.values() if op.kind == kind]

    def to_dict(self) -> dict[str, Callable[..., Any]]:
        """Return a mapping of operation name -> callable for Toolkit/Session injection."""
        return {name: info.func for name, info in self._operations.items()}

    def bind_session(self, session: Any) -> dict[str, Callable[..., Any]]:
        """
        Produce a dictionary of operations configured for the given Session.

        For read-only operations that require the current document (e.g. export_text, ocr),
        if `src_path` is not provided when invoked, `session.current` is automatically supplied.
        """
        ops: dict[str, Callable[..., Any]] = {}
        for name, info in self._operations.items():
            fn = info.func
            if info.kind == "read_only":

                def make_wrapper(inner_fn: Callable[..., Any]) -> Callable[..., Any]:
                    def bound_op(*args: Any, **kwargs: Any) -> Any:
                        if "src_path" not in kwargs and len(args) <= 1:
                            kwargs["src_path"] = getattr(session, "current", None)
                        return inner_fn(*args, **kwargs)

                    bound_op.__name__ = getattr(inner_fn, "__name__", "bound_op")
                    bound_op.__doc__ = getattr(inner_fn, "__doc__", "")
                    return bound_op

                ops[name] = make_wrapper(fn)
            else:
                ops[name] = fn
        return ops

    # ── Dict-like container interface ─────────────────────────────────

    def __getitem__(self, name: str) -> Callable[..., Any]:
        info = self._operations.get(name)
        if info is None:
            raise KeyError(f"Operation {name!r} is not registered.")
        return info.func

    def __setitem__(self, name: str, func: Callable[..., Any]) -> None:
        self.register(name=name, func=func, kind="modifying")

    def __contains__(self, name: object) -> bool:
        return name in self._operations

    def __iter__(self) -> Iterator[str]:
        return iter(self._operations)

    def __len__(self) -> int:
        return len(self._operations)

    def keys(self) -> KeysView[str]:
        return self._operations.keys()

    def values(self) -> list[Callable[..., Any]]:
        return [info.func for info in self._operations.values()]

    def items(self) -> list[tuple[str, Callable[..., Any]]]:
        return [(name, info.func) for name, info in self._operations.items()]

    def __repr__(self) -> str:
        ops = ", ".join(self._operations.keys())
        return f"<OperationsRegistry [{ops}]>"


def get_default_registry() -> OperationsRegistry:
    """Create and return a new OperationsRegistry populated with all default core operations."""
    from pdf_toolkit.core.operations import register_default_operations

    reg = OperationsRegistry()
    register_default_operations(reg)
    return reg


# Global default registry instance
default_registry: OperationsRegistry = get_default_registry()
