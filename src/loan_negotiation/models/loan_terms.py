"""UK mortgage term models for borrower/lender opening positions and agreed deals."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

RateType = Literal["fixed", "tracker", "discount"]
InitialPeriodYears = Literal[2, 5, 10]
RepaymentType = Literal["capital_repayment", "interest_only"]

RATE_TYPES: tuple[RateType, ...] = ("fixed", "tracker", "discount")
INITIAL_PERIODS: tuple[int, ...] = (2, 5, 10)
REPAYMENT_TYPES: tuple[RepaymentType, ...] = ("capital_repayment", "interest_only")


def clamp_preference(value: int) -> int:
    return max(1, min(10, int(value)))


def normalize_feature_preference(raw: object) -> int | None:
    """Map a 1–10 desire for a yes/no product feature (or legacy bool) to an int."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return 8 if raw else 3
    text = str(raw).strip().lower()
    if text in {"true", "yes", "y", "on"}:
        return 8
    if text in {"false", "no", "n", "off"}:
        return 3
    return clamp_preference(int(float(raw)))


def wants_feature(preference: int | None, *, default: bool = False) -> bool:
    """True when preference leans toward the feature being ON (≥6)."""
    if preference is None:
        return default
    return preference >= 6


def normalize_rate_type(raw: object) -> RateType:
    if isinstance(raw, (int, float)):
        # Legacy interest_structure 1–10 continuum.
        n = int(raw)
        if n <= 4:
            return "fixed"
        if n <= 7:
            return "discount"
        return "tracker"
    text = str(raw).strip().lower().replace("-", "_")
    if text in {"fixed", "fix"}:
        return "fixed"
    if text in {"tracker", "variable", "floating"}:
        return "tracker"
    if text in {"discount", "disc"}:
        return "discount"
    if text.isdigit():
        return normalize_rate_type(int(text))
    raise ValueError("rate_type must be fixed, tracker, or discount")


def normalize_initial_period(raw: object) -> int:
    value = int(float(raw))
    if value in INITIAL_PERIODS:
        return value
    # Snap to nearest standard UK deal period.
    return min(INITIAL_PERIODS, key=lambda p: abs(p - value))


def normalize_repayment_type(raw: object) -> RepaymentType:
    text = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"capital_repayment", "repayment", "capital"}:
        return "capital_repayment"
    if text in {"interest_only", "interestonly", "io"}:
        return "interest_only"
    raise ValueError("repayment_type must be capital_repayment or interest_only")


def _validate_min_max(model: BaseModel) -> BaseModel:
    pairs = (
        ("min_downpayment", "max_downpayment", "min_downpayment cannot exceed max_downpayment"),
        (
            "min_interest_rate_pct",
            "max_interest_rate_pct",
            "min_interest_rate_pct cannot exceed max_interest_rate_pct",
        ),
        (
            "min_loan_length_years",
            "max_loan_length_years",
            "min_loan_length_years cannot exceed max_loan_length_years",
        ),
        (
            "min_arrangement_fee",
            "max_arrangement_fee",
            "min_arrangement_fee cannot exceed max_arrangement_fee",
        ),
        ("min_cashback", "max_cashback", "min_cashback cannot exceed max_cashback"),
        (
            "min_overpayment_allowance_pct",
            "max_overpayment_allowance_pct",
            "min_overpayment_allowance_pct cannot exceed max_overpayment_allowance_pct",
        ),
        ("min_erc_pct", "max_erc_pct", "min_erc_pct cannot exceed max_erc_pct"),
    )
    for low_attr, high_attr, message in pairs:
        low = getattr(model, low_attr)
        high = getattr(model, high_attr)
        if low is not None and high is not None and low > high:
            raise ValueError(message)
    return model


class _PartyTermsBase(BaseModel):
    """Opening position for one party in a UK mortgage negotiation."""

    # Deposit (£)
    min_downpayment: float | None = Field(default=None, ge=0)
    max_downpayment: float | None = Field(default=None, ge=0)
    # Pay rate (%)
    min_interest_rate_pct: float | None = Field(default=None, ge=0)
    max_interest_rate_pct: float | None = Field(default=None, ge=0)
    # Full mortgage term (years)
    min_loan_length_years: int | None = Field(default=None, gt=0)
    max_loan_length_years: int | None = Field(default=None, gt=0)
    # Product / arrangement fee (£)
    min_arrangement_fee: float | None = Field(default=None, ge=0)
    max_arrangement_fee: float | None = Field(default=None, ge=0)
    # Cashback incentive (£)
    min_cashback: float | None = Field(default=None, ge=0)
    max_cashback: float | None = Field(default=None, ge=0)
    # Annual overpayment allowance without ERC (%)
    min_overpayment_allowance_pct: float | None = Field(default=None, ge=0, le=100)
    max_overpayment_allowance_pct: float | None = Field(default=None, ge=0, le=100)
    # Early repayment charge during initial deal (%)
    min_erc_pct: float | None = Field(default=None, ge=0, le=100)
    max_erc_pct: float | None = Field(default=None, ge=0, le=100)
    # Categorical preferences
    preferred_rate_type: RateType | None = None
    preferred_initial_period_years: int | None = None
    preferred_repayment_type: RepaymentType | None = None
    # Feature desire 1–10: 1 = strongly prefer OFF, 5 = flexible, 10 = strongly prefer ON
    portable_preference: int | None = Field(default=None, ge=1, le=10)
    free_valuation_preference: int | None = Field(default=None, ge=1, le=10)
    free_legal_preference: int | None = Field(default=None, ge=1, le=10)

    @field_validator("preferred_rate_type", mode="before")
    @classmethod
    def _coerce_pref_rate(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return normalize_rate_type(value)

    @field_validator("preferred_initial_period_years", mode="before")
    @classmethod
    def _coerce_pref_period(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return normalize_initial_period(value)

    @field_validator("preferred_repayment_type", mode="before")
    @classmethod
    def _coerce_pref_repay(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return normalize_repayment_type(value)

    @field_validator(
        "portable_preference",
        "free_valuation_preference",
        "free_legal_preference",
        mode="before",
    )
    @classmethod
    def _coerce_feature_preference(cls, value: object) -> object:
        return normalize_feature_preference(value)

    @model_validator(mode="before")
    @classmethod
    def _legacy_bool_prefs(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        mapping = (
            ("prefer_portable", "portable_preference"),
            ("prefer_free_valuation", "free_valuation_preference"),
            ("prefer_free_legal", "free_legal_preference"),
        )
        out = dict(data)
        for legacy, modern in mapping:
            if modern not in out and legacy in out:
                out[modern] = out.pop(legacy)
            elif legacy in out:
                out.pop(legacy)
        return out

    @model_validator(mode="after")
    def validate_ranges(self) -> "_PartyTermsBase":
        return _validate_min_max(self)  # type: ignore[return-value]


class BorrowerTerms(_PartyTermsBase):
    pass


class LenderTerms(_PartyTermsBase):
    pass


class DealTerms(BaseModel):
    """Agreed UK mortgage package under negotiation."""

    downpayment: float = Field(ge=0, description="Deposit in £")
    interest_rate_pct: float = Field(ge=0)
    loan_length_years: int = Field(gt=0)
    rate_type: RateType = "fixed"
    initial_period_years: int = Field(default=5)
    arrangement_fee: float = Field(default=0, ge=0)
    cashback: float = Field(default=0, ge=0)
    overpayment_allowance_pct: float = Field(default=10, ge=0, le=100)
    erc_pct: float = Field(default=0, ge=0, le=100)
    repayment_type: RepaymentType = "capital_repayment"
    portable: bool = True
    free_valuation: bool = False
    free_legal: bool = False
    consensus_reached: bool = False

    @field_validator("rate_type", mode="before")
    @classmethod
    def coerce_rate_type(cls, value: object) -> RateType:
        return normalize_rate_type(value)

    @field_validator("initial_period_years", mode="before")
    @classmethod
    def coerce_initial_period(cls, value: object) -> int:
        return normalize_initial_period(value)

    @field_validator("repayment_type", mode="before")
    @classmethod
    def coerce_repayment_type(cls, value: object) -> RepaymentType:
        return normalize_repayment_type(value)

    @field_validator("portable", "free_valuation", "free_legal", "consensus_reached", mode="before")
    @classmethod
    def coerce_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n", ""}:
            return False
        raise ValueError(f"expected boolean, got {value!r}")


# Back-compat aliases used by older parsers / tests.
def legacy_interest_type_to_structure(raw: str) -> int | None:
    try:
        kind = normalize_rate_type(raw)
    except ValueError:
        return None
    return {"fixed": 1, "discount": 5, "tracker": 10}[kind]


def clamp_interest_structure(value: int) -> int:
    return clamp_preference(value)
