from .base import Strategy, Signal
from .mean_reversion_rsi import MeanReversionRSI

REGISTRY = {
    "mean_reversion_rsi": MeanReversionRSI,
}


def build(name: str, params: dict) -> Strategy:
    if name not in REGISTRY:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(REGISTRY)}")
    return REGISTRY[name](**params)
