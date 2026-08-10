import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.deadline import build_ics
from app.db import get_db, init_db
from app.models import AuditLog, ClientProfile, Contract
from app.pipeline_runner import run_pipeline_background
from app.schemas_out import (
    AuditHistoryEntryOut,
    AuditLogOut,
    ClientProfileOut,
    ContractOut,
    LoginRequest,
    UsageByAgent,
    UsageSummaryOut,
)
from app.services.auth import SESSION_COOKIE, create_session, destroy_session, require_auth
from app.services.document import extract_contract_text

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Specter AI")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def serve_frontend():
    return FileResponse(STATIC_DIR / "index.html")


# --- Auth -------------------------------------------------------------------


@app.post("/auth/login")
def login(payload: LoginRequest, response: Response):
    token, session = create_session(payload.username, payload.password)
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 8
    )
    return {"display_name": session["display_name"]}


@app.post("/auth/logout")
def logout(response: Response, session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    destroy_session(session_token)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/auth/me")
def me(user: dict = Depends(require_auth)):
    return {"display_name": user["display_name"]}


# --- Contracts ----------------------------------------------------------------


@app.post("/contracts/upload")
async def upload_contract(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    provider: str | None = None,
    model: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_auth),
):
    raw_bytes = await file.read()
    contract_text = extract_contract_text(file.filename, raw_bytes)

    request_id = uuid.uuid4().hex
    contract = Contract(
        raw_text=contract_text,
        status="processing",
        current_stage="queued",
        request_id=request_id,
        created_by=user["display_name"],
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    background_tasks.add_task(
        run_pipeline_background,
        contract.id,
        contract_text,
        provider,
        model,
        request_id,
        user["display_name"],
    )

    return {"contract_id": contract.id, "status": contract.status}


@app.get("/clients", response_model=list[ClientProfileOut])
def list_clients(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    return db.query(ClientProfile).order_by(ClientProfile.name).all()


@app.get("/clients/{client_id}/contracts", response_model=list[ContractOut])
def list_client_contracts(
    client_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)
):
    client = db.get(ClientProfile, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client.contracts


@app.get("/contracts/{contract_id}", response_model=ContractOut)
def get_contract(contract_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@app.get("/contracts/{contract_id}/audit-log", response_model=list[AuditLogOut])
def get_contract_audit_log(
    contract_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)
):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return (
        db.query(AuditLog)
        .filter(AuditLog.contract_id == contract_id)
        .order_by(AuditLog.created_at)
        .all()
    )


@app.get("/contracts/{contract_id}/calendar.ics")
def get_contract_ics(
    contract_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)
):
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    if not contract.deadline or not contract.deadline.get("cancel_by_date"):
        raise HTTPException(status_code=404, detail="No deadline computed for this contract")

    from app.agents.schemas import DeadlineResult

    ics_text = build_ics(contract.contract_type or "Contract", DeadlineResult(**contract.deadline))
    return PlainTextResponse(ics_text, media_type="text/calendar")


# --- History & usage ----------------------------------------------------------


@app.get("/history", response_model=list[AuditHistoryEntryOut])
def get_history(
    limit: int = 200, db: Session = Depends(get_db), user: dict = Depends(require_auth)
):
    rows = (
        db.query(AuditLog, Contract, ClientProfile)
        .outerjoin(Contract, AuditLog.contract_id == Contract.id)
        .outerjoin(ClientProfile, Contract.client_profile_id == ClientProfile.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AuditHistoryEntryOut(
            id=audit.id,
            contract_id=audit.contract_id,
            client_name=client.name if client else None,
            contract_type=contract.contract_type if contract else None,
            agent_name=audit.agent_name,
            confidence=audit.confidence,
            input_tokens=audit.input_tokens,
            output_tokens=audit.output_tokens,
            performed_by=audit.performed_by,
            created_at=audit.created_at,
        )
        for audit, contract, client in rows
    ]


@app.get("/usage/summary", response_model=UsageSummaryOut)
def get_usage_summary(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    rows = (
        db.query(
            AuditLog.agent_name,
            func.count(AuditLog.id),
            func.coalesce(func.sum(AuditLog.input_tokens), 0),
            func.coalesce(func.sum(AuditLog.output_tokens), 0),
        )
        .group_by(AuditLog.agent_name)
        .all()
    )
    by_agent = [
        UsageByAgent(agent_name=name, calls=calls, input_tokens=in_tok, output_tokens=out_tok)
        for name, calls, in_tok, out_tok in rows
    ]
    return UsageSummaryOut(
        total_calls=sum(a.calls for a in by_agent),
        total_input_tokens=sum(a.input_tokens for a in by_agent),
        total_output_tokens=sum(a.output_tokens for a in by_agent),
        by_agent=by_agent,
    )
