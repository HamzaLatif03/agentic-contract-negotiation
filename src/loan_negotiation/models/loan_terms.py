from pydantic import BaseModel, Field, field_validator, model_validator


def clamp_preference(value: int) -> int:
    return max(1, min(10, int(value)))


def clamp_interest_structure(value: int) -> int:
    """Agreed deal point: 1 = fixed, 10 = variable."""
    return max(1, min(10, int(value)))


def legacy_interest_type_to_structure(raw: str) -> int | None:
    normalized = raw.strip().lower()
    if normalized == "fixed":
        return 1
    if normalized == "variable":
        return 10
    return None


class BorrowerTerms(BaseModel):
    min_downpayment: float | None = Field(default=None, ge=0)
    max_downpayment: float | None = Field(default=None, ge=0)
    min_interest_rate_pct: float | None = Field(default=None, ge=0)
    max_interest_rate_pct: float | None = Field(default=None, ge=0)
    min_loan_length_years: int | None = Field(default=None, gt=0)
    max_loan_length_years: int | None = Field(default=None, gt=0)
    fixed_preference: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="How much the borrower wants a fixed rate (1=low, 10=high)",
    )
    variable_preference: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="How much the borrower wants a variable rate (1=low, 10=high)",
    )

    @model_validator(mode="after")
    def validate_ranges(self) -> "BorrowerTerms":
        if (
            self.min_downpayment is not None
            and self.max_downpayment is not None
            and self.min_downpayment > self.max_downpayment
        ):
            raise ValueError("min_downpayment cannot exceed max_downpayment")
        if (
            self.min_interest_rate_pct is not None
            and self.max_interest_rate_pct is not None
            and self.min_interest_rate_pct > self.max_interest_rate_pct
        ):
            raise ValueError("min_interest_rate_pct cannot exceed max_interest_rate_pct")
        if (
            self.min_loan_length_years is not None
            and self.max_loan_length_years is not None
            and self.min_loan_length_years > self.max_loan_length_years
        ):
            raise ValueError("min_loan_length_years cannot exceed max_loan_length_years")
        return self


class LenderTerms(BaseModel):
    min_downpayment: float | None = Field(default=None, ge=0)
    max_downpayment: float | None = Field(default=None, ge=0)
    min_interest_rate_pct: float | None = Field(default=None, ge=0)
    max_interest_rate_pct: float | None = Field(default=None, ge=0)
    min_loan_length_years: int | None = Field(default=None, gt=0)
    max_loan_length_years: int | None = Field(default=None, gt=0)
    fixed_preference: int | None = Field(default=None, ge=1, le=10)
    variable_preference: int | None = Field(default=None, ge=1, le=10)

    @model_validator(mode="after")
    def validate_ranges(self) -> "LenderTerms":
        if (
            self.min_downpayment is not None
            and self.max_downpayment is not None
            and self.min_downpayment > self.max_downpayment
        ):
            raise ValueError("min_downpayment cannot exceed max_downpayment")
        if (
            self.min_interest_rate_pct is not None
            and self.max_interest_rate_pct is not None
            and self.min_interest_rate_pct > self.max_interest_rate_pct
        ):
            raise ValueError("min_interest_rate_pct cannot exceed max_interest_rate_pct")
        if (
            self.min_loan_length_years is not None
            and self.max_loan_length_years is not None
            and self.min_loan_length_years > self.max_loan_length_years
        ):
            raise ValueError("min_loan_length_years cannot exceed max_loan_length_years")
        return self


class DealTerms(BaseModel):
    downpayment: float = Field(ge=0)
    interest_rate_pct: float = Field(ge=0)
    loan_length_years: int = Field(gt=0)
    interest_structure: int = Field(ge=1, le=10)
    consensus_reached: bool = False

    @field_validator("interest_structure", mode="before")
    @classmethod
    def coerce_interest_structure(cls, value: object) -> int:
        if isinstance(value, str):
            legacy = legacy_interest_type_to_structure(value)
            if legacy is not None:
                return legacy
            if value.isdigit():
                return clamp_interest_structure(int(value))
        if isinstance(value, (int, float)):
            raw = int(value)
            if raw == 0:
                return 1
            return clamp_interest_structure(raw)
        raise ValueError("interest_structure must be 1-10 (1=fixed, 10=variable)")
