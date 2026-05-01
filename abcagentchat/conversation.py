from __future__ import annotations

from dataclasses import dataclass, field


Message = dict[str, str]


@dataclass
class Conversation:
    system_prompt: str
    turns: list[Message] = field(default_factory=list)

    def messages_for(self, user_prompt: str) -> list[Message]:
        return [{"role": "system", "content": self.system_prompt}, *self.turns, {"role": "user", "content": user_prompt}]

    def append_exchange(self, user_prompt: str, assistant_content: str) -> None:
        self.turns.append({"role": "user", "content": user_prompt})
        self.turns.append({"role": "assistant", "content": assistant_content})

    def assistant_count(self) -> int:
        return sum(1 for message in self.turns if message.get("role") == "assistant")
