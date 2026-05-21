"""Tests for pydantic schema validators in app/schemas.py."""

import pytest

from app.schemas import ASROptions


class TestASROptionsTemperatures:
    """Tests for ASROptions.temperatures supporting a single float or a list."""

    def test_single_float_is_wrapped_in_list(self) -> None:
        """A scalar float input is normalized to a single-element list."""
        options = ASROptions(temperatures=0.4)
        assert options.temperatures == [0.4]

    def test_list_of_floats_passes_through(self) -> None:
        """A list of floats is preserved as-is."""
        values = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        options = ASROptions(temperatures=values)
        assert options.temperatures == values

    def test_comma_separated_string_is_parsed(self) -> None:
        """A comma-separated string (from a query param) is parsed into floats."""
        options = ASROptions(temperatures="0.0,0.2,0.4,0.6,0.8,1.0")
        assert options.temperatures == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

    def test_comma_separated_string_tolerates_whitespace(self) -> None:
        """Whitespace around comma-separated values is stripped before parsing."""
        options = ASROptions(temperatures="0.0, 0.2 , 0.4")
        assert options.temperatures == [0.0, 0.2, 0.4]

    def test_single_value_string_is_parsed_as_one_element_list(self) -> None:
        """A string with a single numeric value parses to a one-element list."""
        options = ASROptions(temperatures="0.5")
        assert options.temperatures == [0.5]

    def test_invalid_string_raises(self) -> None:
        """A non-numeric token in the string raises a validation error."""
        with pytest.raises(ValueError):
            ASROptions(temperatures="0.0,abc,0.4")
