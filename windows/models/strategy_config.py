from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator, Field


class Position(BaseModel):
    price_difference: float = -1
    stop_loss: float = -1
    take_profit: float = -1


class TradingStrategyConfig(BaseModel):
    symbol: str
    timeframe: str
    timeframe_filters: list[str] = []
    risk_amount: float = 10
    risk_type: str = 'Cash'
    unit_factor: int = 0
    buy_only: bool = True
    sell_only: bool = True
    is_running: bool = False
    next_search_signal_time: datetime = Field(default_factory=datetime.now)
    position: Optional[Position] = None
    default_volume: float = 0.01
    atr_multiplier: float = 5.
    risk_reward: float = 1.
    use_default_volume: bool = False
    use_filter: bool = False
    pivot_distance: int = 9
    pivot_lookback: int = 5
    atr_length: int = 14
    use_atr_min_max_value: bool = False
    atr_min_value: float = 0.00001
    atr_max_value: float = 0.00001
    
    @field_validator('symbol')
    def symbol_is_not_empty(cls, value: str):
        if not value:
            raise ValueError('Vui lòng chọn cặp')
        return value
    