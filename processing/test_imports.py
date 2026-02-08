"""Minimal import test for HEAT processing package."""

from processing.states import AreaState
from processing.buffer import apply_buffer

print("IMPORTS OK")
print([s.value for s in AreaState])
