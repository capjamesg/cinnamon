def change_to_json(database_result):
    columns = [column[0] for column in database_result.description]

    result = [dict(zip(columns, row)) for row in database_result]

    return result
