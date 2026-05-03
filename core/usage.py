from dataclasses import dataclass


@dataclass
class UsageStats:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    elapsed_seconds: float


def format_usage(stats: UsageStats, model: str | None = None) -> str:
    parts = []
    if model:
        short = model.split("/")[-1] if "/" in model else model
        parts.append(short)
    if stats.total_tokens > 0:
        parts.append(f"{stats.total_tokens} tokens ({stats.prompt_tokens}+{stats.completion_tokens})")
    parts.append(f"{stats.elapsed_seconds:.1f}s")
    return " · ".join(parts)
