"""
Log - Моноидный аккумулятор для Writer
======================================
"""

from __future__ import annotations


class Log[A](list[A]):
    """
    Log accumulator for Writer monad.
    
    Обёртка над list с моноидными операциями:
    - empty: пустой лог (просто Log())
    - combine: конкатенация логов
    
    Моноидные законы выполняются:
    - Left identity: Log().combine(x) == x
    - Right identity: x.combine(Log()) == x  
    - Associativity: (x.combine(y)).combine(z) == x.combine(y.combine(z))
    """

    @staticmethod
    def of[T](*items: T) -> Log[T]:
        """Create log with items."""
        return Log[T](items)

    def combine(self, other: Log[A], /) -> Log[A]:
        """
        Combine two logs (monoidal append).
        
        Example:
            Log.of("a", "b").combine(Log.of("c"))  # Log(["a", "b", "c"])
        """
        result: Log[A] = Log(self)
        result.extend(other)
        return result

    def tell(self, item: A, /) -> Log[A]:
        """
        Append single item.
        
        Convenience method equivalent to self.combine(Log.of(item))
        """
        result: Log[A] = Log(self)
        result.append(item)
        return result


__all__ = ("Log",)

