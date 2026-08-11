"""AppState를 감싸는 JSON API. 화면(프론트엔드)은 다음 계획에서 이 라우트를 호출한다."""
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .state import AppState


class UploadRequest(BaseModel):
    a_path: str
    b_path: str
    prev_path: Optional[str] = None


class SpecialLeaveConfirmRequest(BaseModel):
    statuses: List[str]


class BatchAssignRequest(BaseModel):
    keys: List[str]
    survey_name: str


class ContractEditRequest(BaseModel):
    key: str
    start: str
    end: str


class ProceedRequest(BaseModel):
    year: int
    month: int


def create_app(state: Optional[AppState] = None) -> FastAPI:
    if state is None:
        state = AppState()

    app = FastAPI()

    @app.post("/api/upload")
    def upload(req: UploadRequest):
        try:
            return state.load_files(req.a_path, req.b_path, req.prev_path)
        except (ValueError, FileNotFoundError, OSError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/special-leave")
    def get_special_leave():
        return {"groups": state.special_leave_groups()}

    @app.post("/api/special-leave/confirm")
    def confirm_special_leave(req: SpecialLeaveConfirmRequest):
        try:
            state.confirm_special_leave(req.statuses)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"ok": True}

    @app.get("/api/targets")
    def get_targets():
        return {"targets": state.targets(), "survey_names": state.survey_names()}

    @app.post("/api/targets/batch-assign")
    def batch_assign(req: BatchAssignRequest):
        try:
            state.batch_assign(req.keys, req.survey_name)
        except (ValueError, KeyError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"targets": state.targets()}

    @app.post("/api/targets/contract-edit")
    def contract_edit(req: ContractEditRequest):
        try:
            state.edit_contract(req.key, req.start, req.end)
        except (ValueError, KeyError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"targets": state.targets()}

    @app.post("/api/targets/proceed")
    def proceed(req: ProceedRequest):
        try:
            unassigned = state.prepare_calculation(req.year, req.month)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"unassigned_names": unassigned}

    @app.get("/api/confirm-info")
    def confirm_info():
        try:
            return state.confirm_info()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/calculate")
    def calculate():
        errors = state.run_calculation()
        return {"errors": errors}

    @app.get("/api/results")
    def get_results():
        return {"results": state.results_summary()}

    @app.post("/api/download")
    def download():
        try:
            saved = state.download()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"saved_paths": saved}

    @app.get("/api/evidence")
    def get_evidence(key: str):
        data = state.evidence_for(key)
        if data is None:
            raise HTTPException(status_code=404, detail="해당 대상자의 결과를 찾을 수 없습니다.")
        return {"names": state.evidence_names(), **data}

    return app
