from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Adjust these imports to match your engine module names.
# The server expects your engine to expose:
#   - load_rules_workbook(rules_path) -> rules object
#   - process_case(case_data, rules) -> dict with path maps / validation / render-ready data
try:
    from hebisd_review_engine import load_rules_workbook, process_case  # type: ignore
except Exception:  # pragma: no cover
    load_rules_workbook = None
    process_case = None


app = FastAPI(title="HEB ISD Review Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    case: Dict[str, Any] = Field(..., description="Structured case payload")
    rules_path: Optional[str] = Field(
        default="HEB_ISD_Rules_Workbook.xlsx",
        description="Path to the rules workbook inside the server environment",
    )


def _require_engine() -> None:
    if load_rules_workbook is None or process_case is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Engine functions were not found. "
                "Ensure hebisd_review_engine.py exports load_rules_workbook and process_case."
            ),
        )


def _load_rules(rules_path: str):
    _require_engine()
    path = Path(rules_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Rules workbook not found: {rules_path}")
    return load_rules_workbook(str(path))


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    rules = _load_rules(request.rules_path or "HEB_ISD_Rules_Workbook.xlsx")
    result = process_case(request.case, rules)
    return JSONResponse(content=result)


@app.post("/analyze-file")
async def analyze_file(
    case_file: UploadFile = File(...),
    rules_file: UploadFile = File(...),
):
    _require_engine()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        case_path = tmpdir_path / (case_file.filename or "case.json")
        rules_path = tmpdir_path / (rules_file.filename or "rules.xlsx")

        case_bytes = await case_file.read()
        rules_bytes = await rules_file.read()

        case_path.write_bytes(case_bytes)
        rules_path.write_bytes(rules_bytes)

        try:
            case_data = json.loads(case_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON case file: {exc}") from exc

        rules = load_rules_workbook(str(rules_path))
        result = process_case(case_data, rules)
        return JSONResponse(content=result)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
