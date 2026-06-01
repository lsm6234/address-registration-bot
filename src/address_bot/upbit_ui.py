from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import AddressRow, Outcome, RowResult


class UpbitRunMode(str, Enum):
    DRY_RUN = "dry-run-upbit"
    RUN = "run-upbit"


@dataclass(frozen=True)
class UpbitRegistrationOptions:
    mode: UpbitRunMode
    confirm_register: bool = False
    stop_on_error: bool = True

    @property
    def final_click_allowed(self) -> bool:
        return self.mode is UpbitRunMode.RUN and self.confirm_register


class UpbitUi:
    """Conservative Upbit address-book adapter placeholder.

    Upbit registration remains behind a dedicated adapter because live UI selectors
    and Travel Rule prompts must be calibrated from the operator's logged-in PC Web
    session. Until calibrated, every row returns needs_manual instead of guessing.
    """

    def __init__(self, page) -> None:
        self.page = page

    def register_row(self, row: AddressRow, options: UpbitRegistrationOptions) -> RowResult:
        return RowResult(
            row=row,
            outcome=Outcome.NEEDS_MANUAL,
            reason="Upbit UI selector calibration is required before automated address registration",
        )
