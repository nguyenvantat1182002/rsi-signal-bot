from typing import Optional, Union
from datetime import datetime
from pydantic import BaseModel, field_validator, Field


class Position(BaseModel):
    price_difference: Union[int, float] = -1
    stop_loss: Union[int, float] = -1
    take_profit: Union[int, float] = -1


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
    atr_multiplier: int = 5
    risk_reward: float = 1.
    use_default_volume: bool = False
    use_filter: bool = False
    
    @field_validator('symbol')
    def symbol_is_not_empty(cls, value: str):
        if not value:
            raise ValueError('Vui lòng chọn cặp')
        return value
    