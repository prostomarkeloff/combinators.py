from .best import best_of, best_of_many, best_of_w, best_of_many_w
from .vote import vote, vote_w

__all__ = (
    # LazyCoroResult
    "best_of",
    "best_of_many",
    "vote",
    # LazyCoroResultWriter
    "best_of_w",
    "best_of_many_w",
    "vote_w",
)
