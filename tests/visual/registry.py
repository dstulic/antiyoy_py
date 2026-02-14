"""Auto-register all visual tests."""

# Import all visual test modules to trigger registration
from tests.visual import test_one_move_ai  # noqa: F401
from tests.visual import test_one_move_ai_expert  # noqa: F401
from tests.visual import test_ai_spend_money  # noqa: F401
from tests.visual import test_split_province  # noqa: F401
from tests.visual import test_join_province  # noqa: F401

# This module should be imported to ensure all tests are registered
