# src / memory_manager.py

# memory_manager.py

from collections import defaultdict

class MemoryManager:
    def __init__(self):
        self.memory = defaultdict(list)

    def get_customer_id(self, role: str, customer_id: str | None) -> str | None:
        if role == "banker":
            return customer_id if customer_id else "default_banker"
        if role == "customer":
            return customer_id
        return None

    def append_message(self, role: str, customer_id: str | None, message: str):
        cid = self.get_customer_id(role, customer_id)
        if cid is not None:
            self.memory[cid].append(message)

    def get_messages(self, role: str, customer_id: str | None) -> list[str]:
        cid = self.get_customer_id(role, customer_id)
        return self.memory.get(cid, []) if cid else []

    def reset_conversation(self, role: str, customer_id: str | None):
        cid = self.get_customer_id(role, customer_id)
        if cid and cid in self.memory:
            del self.memory[cid]


    