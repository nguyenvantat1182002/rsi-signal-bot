from typing import Optional, Union
from datetime import datetime
from pydantic import BaseModel, field_validator, Field


class Position(BaseModel):
    price_difference: Union[int, float] = -1
    take_profit: Union[int, float] = -1


class TradingStrategyConfig(BaseModel):
    symbol: str
    timeframe: str
    timeframe_filter: str
    risk_amount: int = 10
    unit_factor: int = 0
    auto: bool = True
    max_total_orders: int = 10
    buy_only: bool = True
    sell_only: bool = True
    is_running: bool = False
    next_search_signal_time: datetime = Field(default_factory=datetime.now)
    position: Optional[Position] = None
    divergence_time: Optional[datetime] = None

    @field_validator('symbol')
    def symbol_is_not_empty(cls, value: str):
        if not value:
            raise ValueError('Vui lòng chọn cặp')
        return value
    