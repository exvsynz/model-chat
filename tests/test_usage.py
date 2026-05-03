from core.usage import UsageStats, format_usage


def test_usage_stats_format():
    stats = UsageStats(prompt_tokens=100, completion_tokens=50, total_tokens=150, elapsed_seconds=2.5)
    text = format_usage(stats)
    assert "150 tokens" in text
    assert "2.5s" in text


def test_usage_stats_format_no_tokens():
    stats = UsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0, elapsed_seconds=1.0)
    text = format_usage(stats)
    assert "1.0s" in text


def test_usage_stats_format_with_model():
    stats = UsageStats(prompt_tokens=10, completion_tokens=20, total_tokens=30, elapsed_seconds=0.8)
    text = format_usage(stats, model="deepseek/deepseek-v4-flash")
    assert "deepseek-v4-flash" in text
    assert "30 tokens" in text
