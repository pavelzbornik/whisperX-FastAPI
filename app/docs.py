"""This module provides functions to generate and save API documentation and database schema."""

import json
import os

import yaml
from sqlalchemy import inspect

DOCS_PATH = "app/docs"


def save_openapi_json(app, path=DOCS_PATH):
    """
    Save the OpenAPI documentation of the FastAPI app in JSON and YAML formats.

    Args:
        app: The FastAPI app instance.
        path: The directory path where the documentation files will be saved. Defaults to DOCS_PATH.
    """
    os.makedirs(path, exist_ok=True)
    openapi_data = app.openapi()
    # Change "openapi.json" to desired filename
    with open(f"{path}/openapi.json", "w") as file:
        json.dump(openapi_data, file, indent=2)
    with open(f"{path}/openapi.yaml", "w") as f:
        yaml.dump(openapi_data, f, sort_keys=False)


def generate_markdown_table(model):
    """
    Generate a markdown table for a given SQLAlchemy model.

    Args:
        model: The SQLAlchemy model to generate the table for.

    Returns:
        A string containing the markdown table.
    """
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


def write_markdown_to_file(markdown_tables, path=DOCS_PATH):
    """
    Write the markdown tables to a file.

    Args:
        markdown_tables: The markdown tables to write to the file.
        path: The directory path where the markdown file will be saved. Defaults to DOCS_PATH.
    """
    os.makedirs(path, exist_ok=True)
    with open(f"{path}/db_schema.md", "w") as file:
        file.write(markdown_tables)


def generate_db_schema(models):
    """
    Generate and save the database schema in markdown format.

    Args:
        models: A list of SQLAlchemy models to generate the schema for.
    """
    markdown_tables = "# Database schema \n\n"
    for model in models:
        markdown_tables += generate_markdown_table(model)

    write_markdown_to_file(markdown_tables)
