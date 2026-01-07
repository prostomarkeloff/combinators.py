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
    # Core types
    Expr,
    Flow,
    FlowWriter,
    FlowM,
    Interpreter,
    # Primary functions
    flow,
    flow_writer,
    flow_many,
    flow_many_writer,
    flow_bracket,
    flow_bracket_writer,
    # Aliases: chain
    chain,
    chain_writer,
    chain_many,
    chain_many_writer,
    chain_bracket,
    chain_bracket_writer,
    # Aliases: ast (legacy)
    ast,
    ast_writer,
    ast_many,
    ast_many_writer,
    ast_bracket,
    ast_bracket_writer,
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
    bracket_writer,
    bracket_on_error_writer,
    ensure_writer,
    fallback_writer,
    fallback_chain_writer,
    recover_writer,
    recover_with_writer,
    reject_writer,
    repeat_until_writer,
    retry_writer,
    with_resource_writer,
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
    batch_writer,
    batch_all_writer,
    gather2_writer,
    gather3_writer,
    parallel_writer,
    race_writer,
    race_ok_writer,
    rate_limit_writer,
    zip_par_writer,
    zip_with_writer,
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
    fold_writer,
    partition_writer,
    replicate_writer,
    sequence_writer,
    traverse_writer,
    traverse_par_writer,
    validate_writer,
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
    delay_writer,
    timeout_writer,
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
    bimap_tap_writer,
    filter_or_writer,
    tap_writer,
    tap_async_writer,
    tap_err_writer,
    tap_err_async_writer,
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
    best_of_writer,
    best_of_many_writer,
    vote_writer,
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
    # AST - Core types
    "Expr",
    "Flow",
    "FlowWriter",
    "FlowM",
    "Interpreter",
    # AST - Primary functions
    "flow",
    "flow_writer",
    "flow_many",
    "flow_many_writer",
    "flow_bracket",
    "flow_bracket_writer",
    # AST - Aliases: chain
    "chain",
    "chain_writer",
    "chain_many",
    "chain_many_writer",
    "chain_bracket",
    "chain_bracket_writer",
    # AST - Aliases: ast (legacy)
    "ast",
    "ast_writer",
    "ast_many",
    "ast_many_writer",
    "ast_bracket",
    "ast_bracket_writer",
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
    "bracket_writer",
    "bracket_on_error_writer",
    "ensure_writer",
    "fallback_writer",
    "fallback_chain_writer",
    "recover_writer",
    "recover_with_writer",
    "reject_writer",
    "repeat_until_writer",
    "retry_writer",
    "with_resource_writer",
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
    "batch_writer",
    "batch_all_writer",
    "gather2_writer",
    "gather3_writer",
    "parallel_writer",
    "race_writer",
    "race_ok_writer",
    "rate_limit_writer",
    "zip_par_writer",
    "zip_with_writer",
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
    "fold_writer",
    "partition_writer",
    "replicate_writer",
    "sequence_writer",
    "traverse_writer",
    "traverse_par_writer",
    "validate_writer",
    # Collection - Generic
    "foldM",
    "partitionM",
    "traverseM",
    "validateM",
    # Time - LazyCoroResult
    "delay",
    "timeout",
    # Time - LazyCoroResultWriter
    "delay_writer",
    "timeout_writer",
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
    "bimap_tap_writer",
    "filter_or_writer",
    "tap_writer",
    "tap_async_writer",
    "tap_err_writer",
    "tap_err_async_writer",
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
    "best_of_writer",
    "best_of_many_writer",
    "vote_writer",
    # Errors
    "ConditionNotMetError",
    "TimeoutError",
)
