"""
Lift helpers with semantic namespaces.

Supports three import styles:
    from combinators import lift as L   # Recommended (balance)
    from combinators import lift as _   # Minimal (for hardcore)
    from combinators import lift        # Explicit (for clarity)

Architecture:
- L.up.*    - подъем значений в монаду
- L.down.*  - опускание монады в значение
- L.call()  - вызов функций с лифтингом
- L.w.*     - Writer monad namespace

Examples:
    from combinators import lift as L
    
    # Подъем значений
    user = L.up.pure(User(id=42))
    error = L.up.fail(NotFoundError())
    maybe = L.up.optional(db_result, error=NotFound)
    
    # Вызов функций
    result = L.call(fetch_user, 42)
    
    # Опускание монады
    value = await L.down(result)
    value = await L.down.unsafe(result)
    
    # Writer
    writer = L.w.up.pure(user, log=["created"])
    wr = await L.down(writer)
    
    # Декораторы
    @L.lifted
    async def fetch(): ...
    
    @L.w.lifted
    async def fetch_w(): ...
"""

from __future__ import annotations

# Import namespaces
from . import down as down_ns
from . import up as up_ns
from . import w

# Convenience: most common functions in root for easy access
# (users can still use L.up.pure, L.down.to_result, etc. for clarity)

# From up namespace - подъем значений
from .up import catching, catching_async, fail, from_result, optional, pure

# From call namespace - вызов функций
from .call import call, lifted, wrap_async

# From down namespace - опускание
from .down import or_else, to_result, unsafe

# NOTE: Мы НЕ экспортируем call_ns, down_ns, up_ns - только их содержимое
# Namespaces доступны как: L.up, L.down, L.call (через алиасы ниже)

# Namespace aliases для явного использования
# L.up.* вместо call_ns
up = up_ns
# L.down.* вместо down_ns  
down = down_ns
# NOTE: L.call(func, args) работает через функцию call из корня
# L.call.wrap_async() не поддерживается - используйте прямой импорт или wrap_async из корня

__all__ = (
    # Namespaces (L.up.*, L.down.*, L.w.*)
    "up",
    "down",
    "w",
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
    "lifted",
    "wrap_async",
    # Down
    "to_result",
    "unsafe",
    "or_else",
)
