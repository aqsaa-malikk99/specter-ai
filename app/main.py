from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.agents.deadline import build_ics
from app.db import get_db, init_db
from app.graph import pipeline
from app.models import ClientProfile, Contract

app = FastAPI(title="Contract Renewal & Risk Radar")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.post("/contracts/upload")
async def upload_contract(
    file: UploadFile,
    provider: str | None = None,
    model: str | None = None,
    db: Session = Depends(get_db),
):
    raw_bytes = await file.read()
    try:
        contract_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Only plain-text contracts are supported in Phase 1 (no OCR/PDF parsing yet).",
        )

    result = pipeline.invoke(
        {"contract_text": contract_text, "provider": provider, "model": model, "db": db}
    )

    contract = Contract(
        client_profile_id=result["client_profile_id"],
        is_renewal_of=result.get("is_renewal_of"),
        raw_text=contract_text,
        contract_type=result["intake"].contract_type,
        parties=result["intake"].parties,
        effective_date=result["intake"].effective_date,
        term_length_months=result["intake"].term_length_months,
        extracted_clauses=result["clauses"].model_dump(),
        deadline=result["deadline"].model_dump(),
        diff=result["diff"].model_dump() if result.get("diff") else None,
        risk_flags=result["risk"].model_dump(),
        draft_email=result["draft_email"].model_dump(),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    return {
        "contract_id": contract.id,
        "client_profile_id": contract.client_profile_id,
        "is_renewal_of": contract.is_renewal_of,
        "intake": result["intake"],
        "clauses": result["clauses"],
        "diff": result.get("diff"),
        "risk": result["risk"],
        "deadline": result["deadline"],
        "draft_email": result["draft_email"],
    }


@app.get("/clients")
def list_clients(db: Session = Depends(get_db)):
    return db.query(ClientProfile).all()


@app.get("/clients/{client_id}/contracts")
def list_client_contracts(client_id: str, db: Session = Depends(get_db)):
    client = db.get(ClientProfile, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client.contracts


@app.get("/contracts/{contract_id}")
def get_contract(contract_id: str, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@app.get("/contracts/{contract_id}/calendar.ics")
def get_contract_ics(contract_id: str, db: Session = Depends(get_db)):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not contract.deadline or not contract.deadline.get("cancel_by_date"):
        raise HTTPException(status_code=404, detail="No deadline computed for this contract")

    from app.agents.schemas import DeadlineResult

    ics_text = build_ics(contract.contract_type or "Contract", DeadlineResult(**contract.deadline))
    return PlainTextResponse(ics_text, media_type="text/calendar")
