from __future__ import annotations

import pytest

from core.budget import Budget, BudgetTracker
from core.usage import UsageStats

# --------------------------------------------------------------------------- #
# TestBudget
# --------------------------------------------------------------------------- #


class TestBudget:
    def test_defaults_all_none(self):
        budget = Budget()
        assert budget.max_tokens is None
        assert budget.max_cost_usd is None
        assert budget.warn_at_tokens is None
        assert budget.warn_at_cost_usd is None

    def test_can_set_values(self):
        budget = Budget(
            max_tokens=1000,
            max_cost_usd=0.5,
            warn_at_tokens=800,
            warn_at_cost_usd=0.3,
        )
        assert budget.max_tokens == 1000
        assert budget.max_cost_usd == 0.5
        assert budget.warn_at_tokens == 800
        assert budget.warn_at_cost_usd == 0.3

    def test_partial_values_remain_none(self):
        budget = Budget(max_tokens=5000)
        assert budget.max_tokens == 5000
        assert budget.max_cost_usd is None
        assert budget.warn_at_tokens is None
        assert budget.warn_at_cost_usd is None


# --------------------------------------------------------------------------- #
# TestBudgetTracker
# --------------------------------------------------------------------------- #


class TestBudgetTracker:
    """Test BudgetTracker with various Budget configurations."""

    # ---------- token accumulation ----------

    def test_token_accumulation_single_record(self):
        tracker = BudgetTracker(Budget())
        usage = UsageStats(
            prompt_tokens=100, completion_tokens=50, total_tokens=150, elapsed_seconds=1.0
        )
        tracker.record(usage, model="gpt-4o")
        assert tracker.total_tokens == 150
        assert tracker.estimated_cost_usd > 0

    def test_token_accumulation_multiple_records(self):
        tracker = BudgetTracker(Budget())
        usages = [
            UsageStats(
                prompt_tokens=200, completion_tokens=100, total_tokens=300, elapsed_seconds=1.0
            ),
            UsageStats(
                prompt_tokens=50, completion_tokens=30, total_tokens=80, elapsed_seconds=0.5
            ),
            UsageStats(
                prompt_tokens=0, completion_tokens=500, total_tokens=500, elapsed_seconds=2.0
            ),
        ]
        for u in usages:
            tracker.record(u, model="gpt-4o-mini")
        assert tracker.total_tokens == 300 + 80 + 500  # 880

    def test_token_accumulation_zero_tokens(self):
        tracker = BudgetTracker(Budget())
        usage = UsageStats(
            prompt_tokens=0, completion_tokens=0, total_tokens=0, elapsed_seconds=0.0
        )
        tracker.record(usage, model="gpt-4o")
        assert tracker.total_tokens == 0
        assert tracker.estimated_cost_usd == 0.0

    # ---------- warning threshold ----------

    def test_warning_threshold_triggers_once_then_ok(self):
        """Warning should fire exactly once, then return 'ok' for subsequent calls."""
        tracker = BudgetTracker(Budget(warn_at_tokens=50))
        # First record pushes over warning
        tracker.record(
            UsageStats(
                prompt_tokens=40, completion_tokens=20, total_tokens=60, elapsed_seconds=1.0
            ),
            model="gpt-4o",
        )
        assert tracker.check() == "warning"
        # Second check without accumulating more tokens -> already warned, returns "ok"
        assert tracker.check() == "ok"
        # Even if we accumulate past warning again, should still be "ok"
        tracker.record(
            UsageStats(
                prompt_tokens=100, completion_tokens=100, total_tokens=200, elapsed_seconds=1.0
            ),
            model="gpt-4o",
        )
        assert tracker.check() == "ok"

    def test_warning_by_cost_triggers_once_then_ok(self):
        tracker = BudgetTracker(Budget(warn_at_cost_usd=0.01))
        # Use a model that costs enough to exceed warning in one go
        tracker.record(
            UsageStats(
                prompt_tokens=10000, completion_tokens=5000, total_tokens=15000, elapsed_seconds=1.0
            ),
            model="gpt-4o",  # costs 2.50/1M input, 10.00/1M output -> (10000/1e6*2.5)+(5000/1e6*10)=0.025+0.05=0.075
        )
        assert tracker.check() == "warning"
        assert tracker.check() == "ok"

    # ---------- exceeded threshold ----------

    def test_exceeded_max_tokens(self):
        tracker = BudgetTracker(Budget(max_tokens=100))
        tracker.record(
            UsageStats(
                prompt_tokens=60, completion_tokens=50, total_tokens=110, elapsed_seconds=1.0
            ),
            model="gpt-4o",
        )
        assert tracker.check() == "exceeded"

    def test_exceeded_max_cost(self):
        tracker = BudgetTracker(Budget(max_cost_usd=0.05))
        # Record a usage that definitely exceeds 0.05
        tracker.record(
            UsageStats(
                prompt_tokens=50000,
                completion_tokens=10000,
                total_tokens=60000,
                elapsed_seconds=1.0,
            ),
            model="gpt-4o-mini",  # cost: input 0.15/1M, output 0.60/1M -> 0.15*(50000/1e6) + 0.6*(10000/1e6) = 0.0075+0.006=0.0135 < 0.05? Actually not. Use larger tokens.
        )
        # Use a larger record to exceed cost
        tracker.record(
            UsageStats(
                prompt_tokens=200000,
                completion_tokens=50000,
                total_tokens=250000,
                elapsed_seconds=1.0,
            ),
            model="gpt-4o-mini",
        )
        # Total cost first record 0.0135, second: 0.15*(200000/1e6)+0.6*(50000/1e6)=0.03+0.03=0.06 => total 0.0735
        assert tracker.estimated_cost_usd > 0.05
        assert tracker.check() == "exceeded"

    def test_exceeded_check_multiple_times_returns_exceeded(self):
        tracker = BudgetTracker(Budget(max_tokens=10))
        tracker.record(
            UsageStats(prompt_tokens=5, completion_tokens=10, total_tokens=15, elapsed_seconds=1.0),
            model="gpt-4o",
        )
        assert tracker.check() == "exceeded"
        assert tracker.check() == "exceeded"  # stays exceeded

    # ---------- no-limit budget ----------

    def test_no_limit_budget_never_blocks(self):
        tracker = BudgetTracker(Budget())  # all None
        # Add huge token and cost consumption
        for _ in range(10):
            tracker.record(
                UsageStats(
                    prompt_tokens=1000000,
                    completion_tokens=1000000,
                    total_tokens=2000000,
                    elapsed_seconds=1.0,
                ),
                model="gpt-4o",
            )
        assert tracker.check() == "ok"
        assert tracker.total_tokens == 20_000_000

    # ---------- cost estimation ----------

    def test_cost_estimation_uses_model_specific_rates(self):
        tracker = BudgetTracker(Budget())
        usage = UsageStats(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            total_tokens=2_000_000,
            elapsed_seconds=1.0,
        )
        # gpt-4o: input 2.50, output 10.00 -> 2.50 + 10.00 = 12.50
        tracker.record(usage, model="gpt-4o")
        assert tracker.estimated_cost_usd == pytest.approx(12.50, rel=1e-9)

        # claude-3.5-sonnet: input 3.00, output 15.00 -> 3.00+15.00=18.00
        tracker.record(usage, model="claude-3.5-sonnet")
        assert tracker.estimated_cost_usd == pytest.approx(12.50 + 18.00, rel=1e-9)

    def test_unknown_model_uses_default_rates(self):
        tracker = BudgetTracker(Budget())
        usage = UsageStats(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            total_tokens=2_000_000,
            elapsed_seconds=1.0,
        )
        # default: 2.00 input, 8.00 output -> 2.00 + 8.00 = 10.00
        tracker.record(usage, model="my-custom-model-v2")
        assert tracker.estimated_cost_usd == pytest.approx(10.00, rel=1e-9)

    def test_mixed_models_cost_accumulation(self):
        tracker = BudgetTracker(Budget())
        # gpt-4o-mini: input 0.15/1M, output 0.60/1M
        usage1 = UsageStats(
            prompt_tokens=500_000,
            completion_tokens=500_000,
            total_tokens=1_000_000,
            elapsed_seconds=1.0,
        )
        tracker.record(usage1, model="gpt-4o-mini")
        cost1 = 500_000 / 1_000_000 * 0.15 + 500_000 / 1_000_000 * 0.60  # 0.375
        # deepseek-chat: input 0.14/1M, output 0.28/1M
        usage2 = UsageStats(
            prompt_tokens=1_000_000,
            completion_tokens=200_000,
            total_tokens=1_200_000,
            elapsed_seconds=1.0,
        )
        tracker.record(usage2, model="deepseek-chat")
        cost2 = 1_000_000 / 1_000_000 * 0.14 + 200_000 / 1_000_000 * 0.28  # 0.196
        assert tracker.estimated_cost_usd == pytest.approx(cost1 + cost2, rel=1e-6)

    def test_model_name_with_slash_is_stripped(self):
        tracker = BudgetTracker(Budget())
        usage = UsageStats(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            total_tokens=2_000_000,
            elapsed_seconds=1.0,
        )
        # Use a model path that contains a known pricing key after slash
        tracker.record(usage, model="openai/gpt-4o")
        assert tracker.estimated_cost_usd == pytest.approx(12.50, rel=1e-9)

    # ---------- properties ----------

    def test_total_tokens_property_correct(self):
        tracker = BudgetTracker(Budget())
        tracker.record(
            UsageStats(
                prompt_tokens=100, completion_tokens=200, total_tokens=300, elapsed_seconds=1.0
            ),
            model="gpt-4o",
        )
        tracker.record(
            UsageStats(
                prompt_tokens=50, completion_tokens=25, total_tokens=75, elapsed_seconds=0.5
            ),
            model="gpt-4o",
        )
        assert tracker.total_tokens == 375

    def test_estimated_cost_usd_property_correct(self):
        tracker = BudgetTracker(Budget())
        # gpt-4o: input 2.50/1M, output 10.00/1M → 1M * 2.50 + 1M * 10.00 = 12.50
        tracker.record(
            UsageStats(
                prompt_tokens=1_000_000,
                completion_tokens=1_000_000,
                total_tokens=2_000_000,
                elapsed_seconds=1.0,
            ),
            model="gpt-4o",
        )
        # gpt-4o again: 500K * 2.50 + 200K * 10.00 = 1.25 + 2.00 = 3.25
        tracker.record(
            UsageStats(
                prompt_tokens=500_000,
                completion_tokens=200_000,
                total_tokens=700_000,
                elapsed_seconds=2.0,
            ),
            model="gpt-4o",
        )
        expected = 12.50 + 3.25
        assert tracker.estimated_cost_usd == pytest.approx(expected, rel=1e-6)
