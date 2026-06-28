"""Modelos de dados (dataclasses) que espelham as tabelas do SQLite."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Screen:
    id: int
    name: str
    description: str
    position: int
    folder_name: str
    is_home: int
    is_trash: int = 0

    @classmethod
    def from_row(cls, r) -> "Screen":
        keys = r.keys()
        return cls(
            id=r["id"],
            name=r["name"],
            description=r["description"] or "",
            position=r["position"],
            folder_name=r["folder_name"],
            is_home=r["is_home"],
            is_trash=(r["is_trash"] if "is_trash" in keys else 0),
        )


@dataclass
class Block:
    id: int
    screen_id: int
    name: str
    description: str
    position: int
    folder_name: str

    @classmethod
    def from_row(cls, r) -> "Block":
        return cls(
            id=r["id"],
            screen_id=r["screen_id"],
            name=r["name"],
            description=r["description"] or "",
            position=r["position"],
            folder_name=r["folder_name"],
        )


@dataclass
class Robot:
    id: int
    block_id: int
    name: str
    description: str
    position: int
    folder_name: str
    size: str
    manifest_path: str

    @classmethod
    def from_row(cls, r) -> "Robot":
        return cls(
            id=r["id"],
            block_id=r["block_id"],
            name=r["name"],
            description=r["description"] or "",
            position=r["position"],
            folder_name=r["folder_name"],
            size=r["size"] or "large",
            manifest_path=r["manifest_path"] or "",
        )
