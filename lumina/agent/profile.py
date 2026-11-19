from __future__ import annotations

import json
from pathlib import Path

from lumina.llm.base import ChatMessage


class UserProfileStore:
    """每用户的人物画像：从对话自动抽取的稳定事实，存在 data/profiles.json。"""

    def __init__(self, path: str):
        self.path = Path(path)
        self.data: dict = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                pass

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_facts(self, user_id) -> list[str]:
        return list(self.data.get(str(user_id), {}).get("facts", []))

    def bump(self, user_id, n: int = 5) -> bool:
        """消息计数 +1，达到每 n 条返回 True（触发画像抽取）。"""
        uid = str(user_id)
        entry = self.data.setdefault(uid, {"facts": [], "count": 0})
        entry["count"] = entry.get("count", 0) + 1
        self._save()
        return entry["count"] % n == 0

    def set_facts(self, user_id, facts):
        uid = str(user_id)
        entry = self.data.setdefault(uid, {"facts": [], "count": 0})
        entry["facts"] = list(facts)
        self._save()

    def all_profiles(self) -> dict:
        return {k: v.get("facts", []) for k, v in self.data.items()}


async def extract_facts(provider, facts: list[str], history: str) -> list[str]:
    existing = "\n".join(facts) or "（无）"
    system = (
        "你是人物画像抽取器。从对话历史里提取关于该用户的稳定事实"
        "（昵称、偏好、兴趣、性格、和主人的关系等），每行一条，简短中文，不编造。"
    )
    user = f"已有画像：\n{existing}\n\n对话历史：\n{history}\n\n请输出更新后的画像（保留旧事实、补充新的），每行一条。"
    try:
        resp = await provider.complete(
            [ChatMessage("system", system), ChatMessage("user", user)], []
        )
        return [
            l.strip("- •").strip()
            for l in resp.message.content.splitlines()
            if l.strip()
        ]
    except Exception:  # noqa: BLE001
        return facts
