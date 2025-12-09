# Vulture whitelist for false positives
# These are intentionally unused but required by Python protocols/APIs


# Signal handler signature requires both sig and frame
def _signal_handler_whitelist(sig, frame):
    _ = sig
    _ = frame


# Async context manager protocol requires these parameters
async def _context_manager_whitelist(exc_type, exc_val, exc_tb):
    _ = exc_type
    _ = exc_val
    _ = exc_tb
