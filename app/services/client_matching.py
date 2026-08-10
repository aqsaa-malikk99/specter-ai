"""Fuzzy-match a contract's client name to an existing ClientProfile, or file a new one.

Phase 1 skipped this (spec: "skip company matching at first, just extract fields").
Phase 2 adds it back using a plain string-similarity match — good enough for
distinguishing "Acme Inc." from "Acme, Inc." without pulling in a fuzzy-matching
dependency for a portfolio project.
"""
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models import ClientProfile

MATCH_THRESHOLD = 0.85


def _normalize(name: str) -> str:
    return " ".join(name.lower().replace(",", "").replace(".", "").split())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def find_or_create_client_profile(db: Session, client_name: str) -> ClientProfile:
    """Fuzzy-matches client_name against existing profiles; creates one if none match."""
    best_match: ClientProfile | None = None
    best_score = 0.0

    for profile in db.query(ClientProfile).all():
        score = _similarity(profile.name, client_name)
        if score > best_score:
            best_score = score
            best_match = profile

    if best_match and best_score >= MATCH_THRESHOLD:
        return best_match

    new_profile = ClientProfile(name=client_name)
    db.add(new_profile)
    db.flush()  # assigns new_profile.id without committing the transaction
    return new_profile
