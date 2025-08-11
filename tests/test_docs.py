"""Tests for the docs module."""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest
import yaml

from app.docs import (
    DOCS_PATH,
    generate_db_schema,
    generate_markdown_table,
    save_openapi_json,
    write_markdown_to_file,
)


class TestSaveOpenApiJson:
    """Test cases for save_openapi_json function."""

    def test_save_openapi_json_with_default_path(self):
        """Test saving OpenAPI JSON with default path."""
        mock_app = Mock()
        mock_app.openapi.return_value = {"openapi": "3.0.0", "info": {"title": "Test API"}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Call with explicit path since we can't patch the default
            save_openapi_json(mock_app, temp_dir)
            
            # Verify JSON file was created
            json_path = os.path.join(temp_dir, "openapi.json")
            assert os.path.exists(json_path)
            
            with open(json_path, "r") as f:
                data = json.load(f)
                assert data["openapi"] == "3.0.0"
                assert data["info"]["title"] == "Test API"
            
            # Verify YAML file was created  
            yaml_path = os.path.join(temp_dir, "openapi.yaml")
            assert os.path.exists(yaml_path)
            
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)
                assert data["openapi"] == "3.0.0"
                assert data["info"]["title"] == "Test API"

    def test_save_openapi_json_with_custom_path(self):
        """Test saving OpenAPI JSON with custom path."""
        mock_app = Mock()
        mock_app.openapi.return_value = {"openapi": "3.0.0", "info": {"title": "Test API"}}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_path = os.path.join(temp_dir, "custom_docs")
            save_openapi_json(mock_app, custom_path)
            
            # Verify directory was created
            assert os.path.exists(custom_path)
            
            # Verify files were created in custom path
            json_path = os.path.join(custom_path, "openapi.json")
            yaml_path = os.path.join(custom_path, "openapi.yaml")
            assert os.path.exists(json_path)
            assert os.path.exists(yaml_path)

    def test_save_openapi_json_creates_directory(self):
        """Test that save_openapi_json creates directory if it doesn't exist."""
        mock_app = Mock()
        mock_app.openapi.return_value = {"openapi": "3.0.0"}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_path = os.path.join(temp_dir, "nested", "path", "docs")
            save_openapi_json(mock_app, non_existent_path)
            
            # Verify nested directory was created
            assert os.path.exists(non_existent_path)
            assert os.path.exists(os.path.join(non_existent_path, "openapi.json"))


class TestGenerateMarkdownTable:
    """Test cases for generate_markdown_table function."""

    def test_generate_markdown_table(self):
        """Test generating markdown table for a model."""
        # Create a mock SQLAlchemy model
        mock_model = Mock()
        mock_model.name = "test_table"
        
        # Create mock columns
        mock_column1 = Mock()
        mock_column1.name = "id"
        mock_column1.comment = "Primary key"
        mock_column1.type = "INTEGER"
        mock_column1.nullable = False
        mock_column1.unique = True
        mock_column1.primary_key = True
        
        mock_column2 = Mock()
        mock_column2.name = "name"
        mock_column2.comment = "User name"
        mock_column2.type = "VARCHAR(255)"
        mock_column2.nullable = True
        mock_column2.unique = False
        mock_column2.primary_key = False
        
        # Mock the inspector
        with patch("app.docs.inspect") as mock_inspect:
            mock_inspector = Mock()
            mock_inspector.columns = [mock_column1, mock_column2]
            mock_inspect.return_value = mock_inspector
            
            result = generate_markdown_table(mock_model)
            
            # Verify the result contains expected content
            assert "## Table: test_table" in result
            assert "| Field | Description | Type | Nullable |  Unique | Primary Key |" in result
            assert "| --- | --- | --- | --- | --- | --- |" in result
            assert "| `id` | Primary key | INTEGER | False | True | True |" in result
            assert "| `name` | User name | VARCHAR(255) | True | False | False |" in result

    def test_generate_markdown_table_with_none_comments(self):
        """Test generating markdown table with None comments."""
        mock_model = Mock()
        mock_model.name = "test_table"
        
        mock_column = Mock()
        mock_column.name = "id"
        mock_column.comment = None
        mock_column.type = "INTEGER"
        mock_column.nullable = False
        mock_column.unique = False
        mock_column.primary_key = True
        
        with patch("app.docs.inspect") as mock_inspect:
            mock_inspector = Mock()
            mock_inspector.columns = [mock_column]
            mock_inspect.return_value = mock_inspector
            
            result = generate_markdown_table(mock_model)
            
            assert "| `id` | None | INTEGER | False | False | True |" in result


class TestWriteMarkdownToFile:
    """Test cases for write_markdown_to_file function."""

    def test_write_markdown_to_file_with_default_path(self):
        """Test writing markdown to file with default path."""
        markdown_content = "# Test Content\n\nThis is test markdown."
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Call with explicit path since we can't easily patch the default
            write_markdown_to_file(markdown_content, temp_dir)
            
            file_path = os.path.join(temp_dir, "db_schema.md")
            assert os.path.exists(file_path)
            
            with open(file_path, "r") as f:
                content = f.read()
                assert content == markdown_content

    def test_write_markdown_to_file_with_custom_path(self):
        """Test writing markdown to file with custom path."""
        markdown_content = "# Custom Content"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_path = os.path.join(temp_dir, "custom_docs")
            write_markdown_to_file(markdown_content, custom_path)
            
            # Verify directory was created
            assert os.path.exists(custom_path)
            
            # Verify file content
            file_path = os.path.join(custom_path, "db_schema.md")
            assert os.path.exists(file_path)
            
            with open(file_path, "r") as f:
                content = f.read()
                assert content == markdown_content

    def test_write_markdown_to_file_creates_directory(self):
        """Test that write_markdown_to_file creates directory if it doesn't exist."""
        markdown_content = "# Test"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = os.path.join(temp_dir, "nested", "deep", "path")
            write_markdown_to_file(markdown_content, nested_path)
            
            assert os.path.exists(nested_path)
            assert os.path.exists(os.path.join(nested_path, "db_schema.md"))


class TestGenerateDbSchema:
    """Test cases for generate_db_schema function."""

    def test_generate_db_schema(self):
        """Test generating database schema for multiple models."""
        # Create mock models
        mock_model1 = Mock()
        mock_model1.name = "users"
        
        mock_model2 = Mock()
        mock_model2.name = "tasks"
        
        models = [mock_model1, mock_model2]
        
        with patch("app.docs.generate_markdown_table") as mock_generate:
            mock_generate.side_effect = [
                "## Table: users\n\nUsers table content\n\n",
                "## Table: tasks\n\nTasks table content\n\n"
            ]
            
            with patch("app.docs.write_markdown_to_file") as mock_write:
                generate_db_schema(models)
                
                # Verify generate_markdown_table was called for each model
                assert mock_generate.call_count == 2
                mock_generate.assert_any_call(mock_model1)
                mock_generate.assert_any_call(mock_model2)
                
                # Verify write_markdown_to_file was called with combined content
                mock_write.assert_called_once()
                args, kwargs = mock_write.call_args
                content = args[0]
                
                assert content.startswith("# Database schema \n\n")
                assert "## Table: users" in content
                assert "## Table: tasks" in content

    def test_generate_db_schema_empty_models(self):
        """Test generating database schema with empty models list."""
        models = []
        
        with patch("app.docs.write_markdown_to_file") as mock_write:
            generate_db_schema(models)
            
            mock_write.assert_called_once()
            args, kwargs = mock_write.call_args
            content = args[0]
            
            assert content == "# Database schema \n\n"

    def test_generate_db_schema_single_model(self):
        """Test generating database schema with single model."""
        mock_model = Mock()
        mock_model.name = "single_table"
        
        with patch("app.docs.generate_markdown_table") as mock_generate:
            mock_generate.return_value = "## Table: single_table\n\nContent\n\n"
            
            with patch("app.docs.write_markdown_to_file") as mock_write:
                generate_db_schema([mock_model])
                
                mock_generate.assert_called_once_with(mock_model)
                mock_write.assert_called_once()
                
                args, kwargs = mock_write.call_args
                content = args[0]
                
                assert "# Database schema \n\n## Table: single_table" in content