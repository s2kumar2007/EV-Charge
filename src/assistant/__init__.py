"""
ChargeGap India - Planner Assistant Package.

Provides read-only tool access, district fuzzy resolution, offline intent routing,
and LLM tool-calling backend.
"""
from assistant.resolver import DistrictResolver
from assistant.tools import AssistantTools

__all__ = ["AssistantTools", "DistrictResolver"]
