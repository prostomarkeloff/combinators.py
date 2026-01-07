"""Log - Monoidal accumulator for Writer"""

from __future__ import annotations

class Log[A](list[A]):
    """
    Log accumulator for Writer monad.
    
    Wrapper over list with monoidal operations:
    - empty: empty log (just Log())
    - combine: log concatenation
    
    Monoidal laws are satisfied:
    - Left identity: Log().combine(x) == x
    - Right identity: x.combine(Log()) == x  
    - Associativity: (x.combine(y)).combine(z) == x.combine(y.combine(z))
    """

    @staticmethod
    def of[T](*items: T) -> Log[T]:
        """Create log with items."""
        return Log[T](items)

    def combine(self, other: Log[A], /) -> Log[A]:
        """Combine two logs (monoidal append)."""
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

