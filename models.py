from typing import Optional
from datetime import datetime

from sqlmodel import SQLModel, Field


class Deal(SQLModel, table=True):

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    title: str
    category: str = "Andere"

    shop: str

    original_price: float
    coupon_value: float = 0
    payment_bonus: float = 0

    final_price: float

    coupon_code: Optional[str] = None

    affiliate_url: str
    source_url: Optional[str] = None

    score: int = 0

    active: bool = True

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )
