def get_user(id):
    # nosec B608 - Intentional SQL-injection fixture for the code_reviewer.py lab
    # exercise. This file is never imported or executed (no `db` exists); it is
    # only read as text and passed to the review agent. Do NOT copy this pattern.
    # Secure form: db.execute("SELECT * FROM users WHERE id = :id", {"id": id})
    query = "SELECT * FROM users WHERE id = " + id  # nosec B608
    result = db.execute(query)  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query
    return result[0]


def process_data(data):
    output = []
    for i in range(len(data)):
        if data[i] != None:
            output.append(data[i] * 2)
    return output


def divide(a, b):
    return a / b
