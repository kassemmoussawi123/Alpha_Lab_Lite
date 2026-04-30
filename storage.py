import sqlite3 as sq
import json 
import uuid 
db_name = "alpha_lab_lite.db"

def init_db(): 
    """create table if they don't exist."""
    connect = sq.connect(db_name)
    cursor = connect.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS alpha_lab_lite (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        script_id TEXT NOT NULL, 
        variable_name TEXT NOT NULL,
        variable_json TEXT NOT NULL
    )""")
    connect.commit()
    connect.close()
    
    
def save_result(memory):
    """Save all variables from memory into SQLite and return a script identifier."""
    init_db()
    script_id = str(uuid.uuid4()) # generate a unique script ID
    connection = sq.connect(db_name)
    cursor = connection.cursor()
    for variable_name, values in memory.items():
        values_json = json.dumps(values)

        cursor.execute(
            """
            INSERT INTO alpha_lab_lite (script_id, variable_name, variable_json)
            VALUES (?, ?, ?)
            """,
            (script_id, variable_name, values_json)
        )

    connection.commit()
    connection.close()

    return script_id

def load_result(script_id, variable_names):
    """Load selected variables for a given script identifier from SQLite."""
    init_db()

    connection = sq.connect(db_name)
    cursor = connection.cursor()

    results = {}

    for variable_name in variable_names:
        cursor.execute(
            """
            SELECT variable_json
            FROM alpha_lab_lite
            WHERE script_id = ? AND variable_name = ?
            """,
            (script_id, variable_name)
        )

        row = cursor.fetchone()

        if row is None:
            results[variable_name] = None
        else:
            variable_json = row[0]
            results[variable_name] = json.loads(variable_json)

    connection.close()

    return results