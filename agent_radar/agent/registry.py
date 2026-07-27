"""Tool registry: register schemas, export for the model, dispatch calls."""
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    spec: dict
    fn: Callable[..., str]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, spec: dict, fn: Callable[..., str]) -> None:
        name = spec["function"]["name"]
        self._tools[name] = Tool(name, spec, fn)

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def to_tools_param(self) -> list[dict]:
        return [t.spec for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools[name]
        try:
            return tool.fn(**arguments)
        except Exception as e:  # noqa: BLE001 - return error string to the model
            return f"Tool '{name}' failed: {e}"

    def names(self) -> list[str]:
        return list(self._tools)
