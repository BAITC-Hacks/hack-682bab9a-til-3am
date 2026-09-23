"""AI assistant boundary for the ekt.kz backend."""

from .contracts import AssistantRequest, AssistantResult
from .orchestrator import handle_message

__all__ = ["AssistantRequest", "AssistantResult", "handle_message"]
