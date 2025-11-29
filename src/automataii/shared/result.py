"""
Railway-Oriented Result Types.

Provides Result[T, E] pattern for explicit error handling
without exceptions. Follows Railway-Oriented Programming principles.

Usage:
    def divide(a: float, b: float) -> Result[float, str]:
        if b == 0:
            return Err("Division by zero")
        return Ok(a / b)

    result = divide(10, 2)
    if result.is_ok:
        print(f"Result: {result.value}")
    else:
        print(f"Error: {result.error}")

    # Or use pattern matching (Python 3.10+)
    match divide(10, 2):
        case Ok(value):
            print(f"Result: {value}")
        case Err(error):
            print(f"Error: {error}")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, NoReturn, TypeVar

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """Success case containing a value."""

    value: T

    @property
    def is_ok(self) -> bool:
        return True

    @property
    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        """Returns the contained value."""
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Returns the contained value."""
        return self.value

    def map(self, fn: Callable[[T], U]) -> Ok[U]:
        """Applies fn to the contained value."""
        return Ok(fn(self.value))

    def map_err(self, fn: Callable[[E], U]) -> Ok[T]:
        """Returns self unchanged (no error to map)."""
        return self

    def and_then(self, fn: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Applies fn to the contained value, returning a new Result."""
        return fn(self.value)


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    """Error case containing an error value."""

    error: E

    @property
    def is_ok(self) -> bool:
        return False

    @property
    def is_err(self) -> bool:
        return True

    def unwrap(self) -> NoReturn:
        """Raises an exception since this is an error."""
        raise ValueError(f"Called unwrap on Err: {self.error}")

    def unwrap_or(self, default: T) -> T:  # type: ignore[type-var]
        """Returns the default value."""
        return default

    def map(self, fn: Callable[[T], U]) -> Err[E]:
        """Returns self unchanged (no value to map)."""
        return self

    def map_err(self, fn: Callable[[E], U]) -> Err[U]:
        """Applies fn to the contained error."""
        return Err(fn(self.error))

    def and_then(self, fn: Callable[[T], Result[U, E]]) -> Err[E]:
        """Returns self unchanged (no value to chain)."""
        return self


# Type alias for Result
Result = Ok[T] | Err[E]


def try_result(
    fn: Callable[[], T],
    error_type: type[BaseException] = Exception,
) -> Result[T, str]:
    """
    Wraps a function call in a Result.

    Args:
        fn: Function to call
        error_type: Exception type to catch (default: Exception)

    Returns:
        Ok(result) if successful, Err(str(exception)) if exception raised

    Example:
        result = try_result(lambda: int("42"))  # Ok(42)
        result = try_result(lambda: int("abc"))  # Err("invalid literal...")
    """
    try:
        return Ok(fn())
    except error_type as e:
        return Err(str(e))


def collect_results(results: list[Result[T, E]]) -> Result[list[T], E]:
    """
    Collects a list of Results into a Result of list.

    Returns Ok([values]) if all results are Ok,
    otherwise returns the first Err encountered.

    Example:
        results = [Ok(1), Ok(2), Ok(3)]
        collect_results(results)  # Ok([1, 2, 3])

        results = [Ok(1), Err("error"), Ok(3)]
        collect_results(results)  # Err("error")
    """
    values: list[T] = []
    for result in results:
        if result.is_err:
            return result  # type: ignore
        values.append(result.unwrap())
    return Ok(values)
