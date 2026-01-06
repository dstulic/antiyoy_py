"""Utilities for deterministic random number generation."""

import hashlib
from typing import Optional


def get_deterministic_seed(level_code: str) -> int:
    """
    Generate a deterministic random seed from level code.
    
    This ensures the same level always produces the same random sequence,
    enabling perfect replayability.
    
    Args:
        level_code: The level code string
        
    Returns:
        A 64-bit integer seed derived from the level code hash
    """
    if not level_code:
        return 0
    
    # Hash the level code using MD5
    hash_obj = hashlib.md5(level_code.encode())
    # Use first 8 bytes (64 bits) for seed
    # MD5 gives 16 bytes, we use first 8 for 64-bit integer
    seed_bytes = hash_obj.digest()[:8]
    # Convert to unsigned 64-bit integer
    return int.from_bytes(seed_bytes, byteorder='big', signed=False)
