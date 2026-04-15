"""
Continuo core — reference implementation of the L0-L6 memory stack.

Public API:
    Continuo: the main memory orchestrator class

Example:
    from continuo.core import Continuo

    memory = Continuo()
    system_prompt = await memory.prepare(user_message, base_instructions)
"""

from core.orchestrator import Continuo

__all__ = ["Continuo"]
__version__ = "0.0.1"
