"""
Lift helpers with semantic namespaces.

Supports three import styles:
    from combinators import lift as L   # Recommended (balance)
    from combinators import lift as _   # Minimal (for hardcore)
    from combinators import lift        # Explicit (for clarity)

Architecture:
- L.up.*      - lift values into monad
- L.down.*    - lower monad to value
- L.call()    - call functions with lifting
- L.writer.*  - Writer monad namespace

Examples:
    from combinators import lift as L
    
    # Lift values
    user = L.up.pure(User(id=42))
    error = L.up.fail(NotFoundError())
    maybe = L.up.optional(db_result, error=NotFound)
    
    # Call functions
    result = L.call(fetch_user, 42)
    
    # Lower monad
    value = await L.down(result)
    value = await L.down.unsafe(result)
    
    # Writer
    writer = L.writer.up.pure(user, log=["created"])
    wr = await L.down(writer)
    
    # Decorators
    @L.lifted
    async def fetch(): ...
    
    @L.writer.lifted
    async def fetch_w(): ...
"""

from __future__ import annotations

# Import namespaces
from . import down as down_ns
from . import up as up_ns
from . import writer

# Convenience: most common functions in root for easy access
# (users can still use L.up.pure, L.down.to_result, etc. for clarity)

# From up namespace - lift values
from .up import catching, catching_async, fail, from_result, optional, pure

# From call namespace - call functions
from .call import call, call_catching, lifted, wrap_async

# From down namespace - lower monad
from .down import or_else, to_result, unsafe

# NOTE: We DON'T export call_ns, down_ns, up_ns - only their contents
# Namespaces are available as: L.up, L.down (via aliases below)

# Namespace aliases for explicit use
# L.up.* instead of up_ns
up = up_ns
# L.down.* instead of down_ns  
down = down_ns
# NOTE: L.call(func, args) works through call function from root
# L.call.wrap_async() is not supported - use direct import or wrap_async from root

__all__ = (
    # Namespaces (L.up.*, L.down.*, L.writer.*)
    "up",
    "down",
    "writer",
    # Root functions - most common operations
    # Up
    "pure",
    "fail",
    "from_result",
    "optional",
    "catching",
    "catching_async",
    # Call
    "call",
    "call_catching",
    "lifted",
    "wrap_async",
    # Down
    "to_result",
    "unsafe",
    "or_else",
)
