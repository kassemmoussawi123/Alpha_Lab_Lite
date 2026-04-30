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
    memory = executeScript(request.script)
    script_id = save_result(memory)

    return {
        "message": "Script successfully executed",
        "script_id": script_id,
        "result": script_id
    }


@app.get("/view")
def view_result(script_id: str, variables: str):
    variable_names = variables.split(",")

    data = load_result(script_id, variable_names)

    return data


@app.get("/view/{script_id}")
def view_result_by_path(script_id: str, items: list[str] = Query(...)):
    data = load_result(script_id, items)

    return data
