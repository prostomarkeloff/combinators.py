"""
Combinators library for building resilient async pipelines.

Core building blocks for composing effectful computations with
retry, timeout, fallback, parallel execution, and more.

Architecture:
- Generic combinators (*M functions) work with any monad via extract + wrap pattern
- Sugar functions for LazyCoroResult (no suffix)
- Sugar functions for LazyCoroResultWriter (*_w suffix)
"""

# Core types
from ._types import LCR, NoError, Predicate, Route, Selector

# Internal helpers (for custom monads)
from . import _helpers

# AST builder (Flow API)
from .ast import (
    # LazyCoroResult
    ast,
    ast_bracket,
    ast_many,
    Expr,
    Flow,
    # LazyCoroResultWriter
    ast_w,
    ast_bracket_w,
    ast_many_w,
    FlowW,
    # Generic
    FlowM,
    Interpreter,
)

# Lift helpers (reduce boilerplate)
from . import lift
from .lift import (
    call,
    catching,
    catching_async,
    fail,
    from_result,
    lifted,
    optional,
    pure,
    wrap_async,
)

# Writer monad
from . import writer
from .writer import LazyCoroResultWriter, Log, WriterResult

# Control flow
from .control import (
    RepeatPolicy,
    RetryPolicy,
    # LazyCoroResult
    bracket,
    bracket_on_error,
    ensure,
    fallback,
    fallback_chain,
    fallback_with,
    recover,
    recover_with,
    reject,
    repeat_until,
    retry,
    with_resource,
    # LazyCoroResultWriter
    bracket_w,
    bracket_on_error_w,
    ensure_w,
    fallback_w,
    fallback_chain_w,
    recover_w,
    recover_with_w,
    reject_w,
    repeat_until_w,
    retry_w,
    with_resource_w,
    # Generic
    bracketM,
    ensureM,
    fallbackM,
    fallback_chainM,
    recoverM,
    recover_withM,
    rejectM,
    repeat_untilM,
    retryM,
)

# Concurrency
from .concurrency import (
    RaceOkPolicy,
    RateLimitPolicy,
    # LazyCoroResult
    batch,
    batch_all,
    gather2,
    gather3,
    parallel,
    race,
    race_ok,
    rate_limit,
    zip_par,
    zip_with,
    # LazyCoroResultWriter
    batch_w,
    batch_all_w,
    gather2_w,
    gather3_w,
    parallel_w,
    race_w,
    race_ok_w,
    rate_limit_w,
    zip_par_w,
    zip_with_w,
    # Generic
    batchM,
    batch_allM,
    gather2M,
    gather3M,
    parallelM,
    raceM,
    race_okM,
    rate_limitM,
    zip_parM,
)

# Collection operations
from .collection import (
    # LazyCoroResult
    fold,
    partition,
    replicate,
    sequence,
    traverse,
    traverse_par,
    validate,
    # LazyCoroResultWriter
    fold_w,
    partition_w,
    replicate_w,
    sequence_w,
    traverse_w,
    traverse_par_w,
    validate_w,
    # Generic
    foldM,
    partitionM,
    traverseM,
    validateM,
)

# Time operations
from .time import (
    # LazyCoroResult
    delay,
    timeout,
    # LazyCoroResultWriter
    delay_w,
    timeout_w,
    # Generic
    delayM,
    timeoutM,
)

# Transform/effects
from .transform import (
    # LazyCoroResult
    bimap_tap,
    filter_or,
    tap,
    tap_async,
    tap_err,
    tap_err_async,
    # LazyCoroResultWriter
    bimap_tap_w,
    filter_or_w,
    tap_w,
    tap_async_w,
    tap_err_w,
    tap_err_async_w,
    # Generic
    tapM,
    tap_asyncM,
    tap_errM,
    tap_err_asyncM,
)

# Selection
from .selection import (
    # LazyCoroResult
    best_of,
    best_of_many,
    vote,
    # LazyCoroResultWriter
    best_of_w,
    best_of_many_w,
    vote_w,
)

# Errors
from ._errors import ConditionNotMetError, TimeoutError

__all__ = (
    # Types
    "LCR",
    "NoError",
    "Predicate",
    "Route",
    "Selector",
    # Internal helpers (for custom monads)
    "_helpers",
    # AST - LazyCoroResult
    "Expr",
    "Flow",
    "ast",
    "ast_bracket",
    "ast_many",
    # AST - LazyCoroResultWriter
    "FlowW",
    "ast_w",
    "ast_bracket_w",
    "ast_many_w",
    # AST - Generic
    "FlowM",
    "Interpreter",
    # Lift module (namespace import - preferred)
    "lift",
    # Lift functions (direct import)
    "call",
    "catching",
    "catching_async",
    "fail",
    "from_result",
    "lifted",
    "optional",
    "pure",
    "wrap_async",
    # Writer module
    "writer",
    "LazyCoroResultWriter",
    "Log",
    "WriterResult",
    # Control - LazyCoroResult
    "RepeatPolicy",
    "RetryPolicy",
    "bracket",
    "bracket_on_error",
    "ensure",
    "fallback",
    "fallback_chain",
    "fallback_with",
    "recover",
    "recover_with",
    "reject",
    "repeat_until",
    "retry",
    "with_resource",
    # Control - LazyCoroResultWriter
    "bracket_w",
    "bracket_on_error_w",
    "ensure_w",
    "fallback_w",
    "fallback_chain_w",
    "recover_w",
    "recover_with_w",
    "reject_w",
    "repeat_until_w",
    "retry_w",
    "with_resource_w",
    # Control - Generic
    "bracketM",
    "ensureM",
    "fallbackM",
    "fallback_chainM",
    "recoverM",
    "recover_withM",
    "rejectM",
    "repeat_untilM",
    "retryM",
    # Concurrency - LazyCoroResult
    "RaceOkPolicy",
    "RateLimitPolicy",
    "batch",
    "batch_all",
    "gather2",
    "gather3",
    "parallel",
    "race",
    "race_ok",
    "rate_limit",
    "zip_par",
    "zip_with",
    # Concurrency - LazyCoroResultWriter
    "batch_w",
    "batch_all_w",
    "gather2_w",
    "gather3_w",
    "parallel_w",
    "race_w",
    "race_ok_w",
    "rate_limit_w",
    "zip_par_w",
    "zip_with_w",
    # Concurrency - Generic
    "batchM",
    "batch_allM",
    "gather2M",
    "gather3M",
    "parallelM",
    "raceM",
    "race_okM",
    "rate_limitM",
    "zip_parM",
    # Collection - LazyCoroResult
    "fold",
    "partition",
    "replicate",
    "sequence",
    "traverse",
    "traverse_par",
    "validate",
    # Collection - LazyCoroResultWriter
    "fold_w",
    "partition_w",
    "replicate_w",
    "sequence_w",
    "traverse_w",
    "traverse_par_w",
    "validate_w",
    # Collection - Generic
    "foldM",
    "partitionM",
    "traverseM",
    "validateM",
    # Time - LazyCoroResult
    "delay",
    "timeout",
    # Time - LazyCoroResultWriter
    "delay_w",
    "timeout_w",
    # Time - Generic
    "delayM",
    "timeoutM",
    # Transform - LazyCoroResult
    "bimap_tap",
    "filter_or",
    "tap",
    "tap_async",
    "tap_err",
    "tap_err_async",
    # Transform - LazyCoroResultWriter
    "bimap_tap_w",
    "filter_or_w",
    "tap_w",
    "tap_async_w",
    "tap_err_w",
    "tap_err_async_w",
    # Transform - Generic
    "tapM",
    "tap_asyncM",
    "tap_errM",
    "tap_err_asyncM",
    # Selection - LazyCoroResult
    "best_of",
    "best_of_many",
    "vote",
    # Selection - LazyCoroResultWriter
    "best_of_w",
    "best_of_many_w",
    "vote_w",
    # Errors
    "ConditionNotMetError",
    "TimeoutError",
)
