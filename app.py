from fastapi import FastAPI, HTTPException
from fastapi import Query
from pydantic import BaseModel, Field
import math
from research import run as run_research

from engine import executeScript
from storage import save_result, load_result

app = FastAPI()


class ExecuteRequest(BaseModel):
    script: str


@app.post("/execute")
def execute_script(request: ExecuteRequest):
    """ Execute provided script and return id"""
    try:
        memory = executeScript(request.script)
        script_id = save_result(memory)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return {
        "message": "Script successfully executed",
        "script_id": script_id,
        "result": script_id
    }



@app.get("/view/{script_id}")
def view_result_by_path(script_id: str, items: list[str] = Query(...)):
    """load the needed  variables from saved  script execution
    this route matches the pdf  example:
    /view/{script_id}?items=price&items=result
    rhe user provides:
    - script_identifier : use unique id  returned by /execute
    - items:  1 or more variable names to load
    rhe function returns the saved values from sqlite dataBase .
    """

    data = load_result(script_id, items)

    return clean_json(data)


def clean_json(value):
    if isinstance(value, dict):
        return {k:clean_json(v) for k,v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value

class ResearchRequest(BaseModel):
    dataset: str = "OneMinuteGoldPrices"
    rounds: int = Field(default=3, ge=1, le=6)

@app.post("/research")
def research_experiment(request: ResearchRequest):
    """Offline demo only. Use CLI for explicitly configured LLM execution."""
    try:
        return run_research(label=request.dataset, rounds=request.rounds)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


class AnalyzeRequest(BaseModel):
    script: str = Field(min_length=1, max_length=10000)
    previous_scripts: list[str] = Field(default_factory=list, max_length=6)

@app.post("/analyze")
def analyze_strategy(request: AnalyzeRequest):
    """Check expression complexity and similarity without executing a strategy."""
    from strategy_checks import check_strategy
    try:
        return check_strategy(request.script, request.previous_scripts)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
