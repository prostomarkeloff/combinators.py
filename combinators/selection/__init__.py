from .best import best_of, best_of_many, best_of_writer, best_of_many_writer
from .vote import vote, vote_writer

__all__ = (
    # LazyCoroResult
    "best_of",
    "best_of_many",
    "vote",
    # LazyCoroResultWriter
    "best_of_writer",
    "best_of_many_writer",
    "vote_writer",
)
