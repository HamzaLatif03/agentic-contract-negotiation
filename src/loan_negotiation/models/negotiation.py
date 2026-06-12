from pydantic import BaseModel, Field

from loan_negotiation.models.loan_terms import DealTerms


class RoundOffer(BaseModel):
    round_number: int = Field(ge=1)
    proposer: str
    offer: DealTerms
    message: str = ""


class NegotiationState(BaseModel):
    current_round: int = 0
    max_rounds: int = 10
    offers: list[RoundOffer] = Field(default_factory=list)
    latest_deal: DealTerms | None = None
    consensus_reached: bool = False
