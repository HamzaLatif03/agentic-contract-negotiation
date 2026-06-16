from loan_negotiation.models.loan_terms import BorrowerTerms, LenderTerms
from loan_negotiation.services.intake import borrower_missing_fields, intake_complete, lender_missing_fields
from loan_negotiation.workflow.samples import sample_borrower, sample_lender


def test_borrower_missing_fields_when_empty():
    missing = borrower_missing_fields(BorrowerTerms())

    assert len(missing) == 4


def test_lender_missing_fields_when_empty():
    missing = lender_missing_fields(LenderTerms())

    assert len(missing) >= 3


def test_intake_complete_when_all_fields_set():
    assert intake_complete(sample_borrower(), sample_lender()) is True


def test_intake_incomplete_when_borrower_partial():
    borrower = sample_borrower()
    borrower.fixed_preference = None

    assert intake_complete(borrower, sample_lender()) is False
