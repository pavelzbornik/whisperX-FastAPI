from sqlalchemy import inspect
import json
import yaml


def save_openapi_json(app, path):
    openapi_data = app.openapi()
    # Change "openapi.json" to desired filename
    with open(f"{path}openapi.json", "w") as file:
        json.dump(openapi_data, file, indent=2)
    with open(f"{path}openapi.yaml", "w") as f:
        yaml.dump(openapi_data, f, sort_keys=False)


def generate_markdown_table(model):
    inspector = inspect(model)
    columns = inspector.columns

    column_names = [column.name for column in columns]
    column_descriptions = [column.comment for column in columns]
    column_types = [str(column.type) for column in columns]
    column_nullable = [column.nullable for column in columns]
    column_unique = [column.unique for column in columns]
    column_primary_key = [column.primary_key for column in columns]

    table_name = model.name

    # Transpose the table
    markdown_table = f"## Table: {table_name}\n\n"
    markdown_table += (
        "| Field | Description | Type | Nullable |  Unique | Primary Key |\n"
    )
    markdown_table += "| --- | --- | --- | --- | --- | --- |\n"
    for i in range(len(column_names)):
        markdown_table += f"| `{column_names[i]}` | {column_descriptions[i]} | {column_types[i]} | {column_nullable[i]} | {column_unique[i]} | {column_primary_key[i]} |\n"

    return markdown_table


def write_markdown_to_file(markdown_table, filename):
    with open(filename, "w") as file:
        file.write(markdown_table)


def generate_db_schema(models, filename):
    markdown_table = "# Database schema \n\n"
    for model in models:
        markdown_table += generate_markdown_table(model)

    write_markdown_to_file(markdown_table, filename)
