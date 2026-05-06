"""
Bourdon core — reference implementation of the L0-L6 memory stack.

Public API:
    Bourdon: the main memory orchestrator class

Example:
    from core import Bourdon

    memory = Bourdon()
    system_prompt = await memory.prepare(user_message, base_instructions)
"""

from core.orchestrator import Bourdon

__all__ = ["Bourdon"]
__version__ = "0.0.1"
