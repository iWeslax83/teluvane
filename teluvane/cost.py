# teluvane/teluvane/cost.py
"""Static USD-per-million-token pricing for known models, used to compute cost_usd on
llm_call events when a caller supplies model + token counts but not an explicit cost.
Unknown models simply get no computed cost (None), never a guess."""

from typing import Optional

# (input $/1M tokens, output $/1M tokens)
PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "claude-opus-5": (15.0, 75.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-fable-5": (0.8, 4.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.4, 1.6),
    "o3": (2.0, 8.0),
}


def compute_cost(
    model: Optional[str], input_tokens: Optional[int], output_tokens: Optional[int]
) -> Optional[float]:
    if not model or model not in PRICING_PER_MILLION:
        return None
    in_rate, out_rate = PRICING_PER_MILLION[model]
    return round(
        (input_tokens or 0) * in_rate / 1_000_000 + (output_tokens or 0) * out_rate / 1_000_000, 8
    )
