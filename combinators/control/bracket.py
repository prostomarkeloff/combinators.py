"""
Bracket combinators
===================

Комбинаторы для resource management с extract + wrap паттерном.
"""

from __future__ import annotations

import typing
from collections.abc import Awaitable, Callable, Coroutine

from kungfu import Error, LazyCoroResult, Ok, Result

from ..writer import LazyCoroResultWriter, Log, WriterResult


# ============================================================================
# Generic combinators (extract + wrap pattern)
# ============================================================================


def bracketM[M, T, R, E, RawT, RawR](
    acquire: Callable[[], Coroutine[typing.Any, typing.Any, RawT]],
    *,
    extract_acquire: Callable[[RawT], Result[T, E]],
    get_resource: Callable[[RawT], T],
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], Callable[[], Coroutine[typing.Any, typing.Any, RawR]]],
    combine_err: Callable[[E], RawR],
    wrap: Callable[[Callable[[], Coroutine[typing.Any, typing.Any, RawR]]], M],
) -> M:
    """
    Generic bracket combinator.
    
    Resource management: acquire → use → release (always, even on error).
    """
    
    async def run() -> RawR:
        acquire_raw = await acquire()
        acquire_result = extract_acquire(acquire_raw)
        
        match acquire_result:
            case Error(e):
                return combine_err(e)
            case Ok(_):
                resource = get_resource(acquire_raw)
                try:
                    use_raw = await use(resource)()
                    return use_raw
                finally:
                    try:
                        await release(resource)
                    except Exception:
                        pass
    
    return wrap(run)


# ============================================================================
# Sugar for LazyCoroResult
# ============================================================================


def bracket[T, R, E](
    acquire: LazyCoroResult[T, E],
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResult[R, E]],
) -> LazyCoroResult[R, E]:
    """Resource management: acquire → use → release (always)."""
    
    def extract(r: Result[T, E]) -> Result[T, E]:
        return r
    
    def get_resource(r: Result[T, E]) -> T:
        return r.unwrap()
    
    def combine_err(e: E) -> Result[R, E]:
        return Error(e)
    
    return bracketM(
        acquire,
        extract_acquire=extract,
        get_resource=get_resource,
        release=release,
        use=use,
        combine_err=combine_err,
        wrap=LazyCoroResult,
    )


def bracket_on_error[T, R, E](
    acquire: LazyCoroResult[T, E],
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResult[R, E]],
) -> LazyCoroResult[R, E]:
    """Like bracket, but only releases on error."""
    
    async def run() -> Result[R, E]:
        acquire_result = await acquire()
        
        match acquire_result:
            case Error(e):
                return Error(e)
            case Ok(resource):
                use_result = await use(resource)()
                
                match use_result:
                    case Ok(value):
                        return Ok(value)
                    case Error(e):
                        try:
                            await release(resource)
                        except Exception:
                            pass
                        return Error(e)
    
    return LazyCoroResult(run)


def with_resource[T, R, E](
    resource: T,
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResult[R, E]],
) -> LazyCoroResult[R, E]:
    """Bracket for already-acquired resource."""
    
    async def run() -> Result[R, E]:
        try:
            use_result = await use(resource)()
            return use_result
        finally:
            try:
                await release(resource)
            except Exception:
                pass
    
    return LazyCoroResult(run)


# ============================================================================
# Sugar for LazyCoroResultWriter
# ============================================================================


def bracket_w[T, R, E, W](
    acquire: LazyCoroResultWriter[T, E, W],
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResultWriter[R, E, W]],
) -> LazyCoroResultWriter[R, E, W]:
    """Resource management with log merging."""
    
    async def run() -> WriterResult[R, E, Log[W]]:
        acquire_wr = await acquire()
        
        match acquire_wr.result:
            case Error(e):
                return WriterResult(Error(e), acquire_wr.log)
            case Ok(resource):
                try:
                    use_wr = await use(resource)()
                    merged_log = acquire_wr.log.combine(use_wr.log)
                    return WriterResult(use_wr.result, merged_log)
                finally:
                    try:
                        await release(resource)
                    except Exception:
                        pass
    
    return LazyCoroResultWriter(run)


def bracket_on_error_w[T, R, E, W](
    acquire: LazyCoroResultWriter[T, E, W],
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResultWriter[R, E, W]],
) -> LazyCoroResultWriter[R, E, W]:
    """Like bracket_w, but only releases on error."""
    
    async def run() -> WriterResult[R, E, Log[W]]:
        acquire_wr = await acquire()
        
        match acquire_wr.result:
            case Error(e):
                return WriterResult(Error(e), acquire_wr.log)
            case Ok(resource):
                use_wr = await use(resource)()
                merged_log = acquire_wr.log.combine(use_wr.log)
                
                match use_wr.result:
                    case Ok(value):
                        return WriterResult(Ok(value), merged_log)
                    case Error(e):
                        try:
                            await release(resource)
                        except Exception:
                            pass
                        return WriterResult(Error(e), merged_log)
    
    return LazyCoroResultWriter(run)


def with_resource_w[T, R, E, W](
    resource: T,
    *,
    release: Callable[[T], Awaitable[None]],
    use: Callable[[T], LazyCoroResultWriter[R, E, W]],
) -> LazyCoroResultWriter[R, E, W]:
    """Bracket for already-acquired resource with log."""
    
    async def run() -> WriterResult[R, E, Log[W]]:
        try:
            use_wr = await use(resource)()
            return use_wr
        finally:
            try:
                await release(resource)
            except Exception:
                pass
    
    return LazyCoroResultWriter(run)


__all__ = (
    "bracket",
    "bracket_on_error",
    "with_resource",
    "bracket_w",
    "bracket_on_error_w",
    "with_resource_w",
    "bracketM",
)
