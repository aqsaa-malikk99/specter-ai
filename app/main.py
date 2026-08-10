from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.agents.deadline import build_ics
from app.db import get_db, init_db
from app.graph import pipeline
from app.models import Contract

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
        {"contract_text": contract_text, "provider": provider, "model": model}
    )

    contract = Contract(
        raw_text=contract_text,
        contract_type=result["intake"].contract_type,
        parties=result["intake"].parties,
        effective_date=result["intake"].effective_date,
        term_length_months=result["intake"].term_length_months,
        extracted_clauses=result["clauses"].model_dump(),
        deadline=result["deadline"].model_dump(),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    return {
        "contract_id": contract.id,
        "intake": result["intake"],
        "clauses": result["clauses"],
        "deadline": result["deadline"],
    }


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
