import pytest

from lead_manager import DuplicateLeadError, LeadError, LeadManager


@pytest.fixture
def manager(tmp_path):
    with LeadManager(tmp_path / "leads.db") as lead_manager:
        yield lead_manager


def test_create_lead_stores_all_fields(manager):
    lead = manager.create_lead("Ada Lovelace", "+1 (212) 555-0100", "referral")

    assert lead.id > 0
    assert lead.name == "Ada Lovelace"
    assert lead.phone_number == "+1 (212) 555-0100"
    assert lead.source == "referral"
    assert lead.status == "new"
    assert manager.get_lead(lead.id) == lead


def test_duplicate_normalized_phone_number_is_rejected(manager):
    manager.create_lead("First Lead", "+1 (212) 555-0100", "website")

    with pytest.raises(DuplicateLeadError):
        manager.create_lead("Duplicate", "1-212-555-0100", "event")

    assert len(manager.list_leads()) == 1


def test_change_status_supports_each_status(manager):
    lead = manager.create_lead("Grace Hopper", "202.555.0142", "conference")

    for status in ("contacted", "booked", "closed", "new"):
        lead = manager.change_status(lead.id, status)
        assert lead.status == status
        assert manager.get_lead(lead.id).status == status


def test_unknown_status_is_rejected(manager):
    lead = manager.create_lead("Katherine Johnson", "2025550187", "referral")

    with pytest.raises(LeadError, match="Status must be one of"):
        manager.change_status(lead.id, "lost")

    assert manager.get_lead(lead.id).status == "new"
