"""Constructor injection designed with OOP in mind."""
import warnings

from _dependencies.injector import Injector
from _dependencies.objects.package import Package
from _dependencies.objects.shield import shield
from _dependencies.objects.this import this
from _dependencies.objects.value import value


__all__ = ("Injector", "Package", "this", "value", "shield")


warnings.warn(
    "Do not use dependencies package. Use https://github.com/hynek/svcs package instead.",
    DeprecationWarning,
    stacklevel=2,
)
