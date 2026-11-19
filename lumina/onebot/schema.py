from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RiskLevel = Literal["safe", "risky", "forbidden"]


@dataclass
class ActionParam:
    name: str
    type: str
    description: str
    required: bool = False


@dataclass
class ActionSchema:
    name: str
    category: str
    description: str
    risk: RiskLevel
    params: list[ActionParam]


def load_actions(path: str | Path) -> list[ActionSchema]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        ActionSchema(
            name=a["name"],
            category=a["category"],
            description=a["description"],
            risk=a["risk"],
            params=[ActionParam(**p) for p in a.get("params", [])],
        )
        for a in data["actions"]
    ]


def to_openai_tool(action: ActionSchema) -> dict:
    properties = {
        p.name: {"type": p.type, "description": p.description} for p in action.params
    }
    required = [p.name for p in action.params if p.required]
    return {
        "type": "function",
        "function": {
            "name": action.name,
            "description": action.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
