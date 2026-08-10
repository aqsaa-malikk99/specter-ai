"""Find a prior contract on file that the newly-uploaded one is likely renewing.

Heuristic: most recent *completed* contract filed under the same client
profile with the same contract_type. This is deliberately simple — good
enough to trigger the Diff Agent for the "real SaaS contract + lightly-
edited renewal" test case in the phased build plan, without building a full
contract-matching model.
"""
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Contract


def find_prior_contract(
    db: Session,
    client_profile_id: str,
    contract_type: str | None,
    exclude_contract_id: str | None = None,
) -> Contract | None:
    if not contract_type:
        return None
    query = db.query(Contract).filter(
        Contract.client_profile_id == client_profile_id,
        Contract.contract_type == contract_type,
        Contract.status == "completed",
    )
    if exclude_contract_id:
        query = query.filter(Contract.id != exclude_contract_id)
    return query.order_by(desc(Contract.created_at)).first()
