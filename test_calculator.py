import pytest

from calculator import add, divide, multiply, power, subtract


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(7, 4) == 3


def test_multiply():
    assert multiply(3, 4) == 12


def test_power_with_positive_exponent():
    assert power(2, 3) == 8


def test_power_with_negative_exponent():
    assert power(2, -2) == 0.25


def test_divide():
    assert divide(10, 2) == 5


def test_divide_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(1, 0)
