from fastapi import FastAPI
from fastapi import Query
from pydantic import BaseModel

from engine import executeScript
from storage import save_result, load_result

app = FastAPI()


class ExecuteRequest(BaseModel):
    script: str


@app.post("/execute")
def execute_script(request: ExecuteRequest):
    """ Execute provided script and return id"""
    memory = executeScript(request.script)
    script_id = save_result(memory)

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

    return data
