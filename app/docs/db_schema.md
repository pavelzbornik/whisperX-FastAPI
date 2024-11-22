# Database schema

## Table: tasks

| Field | Description | Type | Nullable |  Unique | Primary Key |
| --- | --- | --- | --- | --- | --- |
| `id` | Unique identifier for each task (Primary Key) | INTEGER | False | None | True |
| `uuid` | Universally unique identifier for each task | VARCHAR | True | None | False |
| `status` | Current status of the task | VARCHAR | True | None | False |
| `result` | JSON data representing the result of the task | JSON | True | None | False |
| `file_name` | Name of the file associated with the task | VARCHAR | True | None | False |
| `url` | URL of the file associated with the task | VARCHAR | True | None | False |
| `audio_duration` | Duration of the audio in seconds | FLOAT | True | None | False |
| `language` | Language of the file associated with the task | VARCHAR | True | None | False |
| `task_type` | Type/category of the task | VARCHAR | True | None | False |
| `task_params` | Parameters of the task | JSON | True | None | False |
| `duration` | Duration of the task execution | FLOAT | True | None | False |
| `start_time` | Start time of the task execution | DATETIME | True | None | False |
| `end_time` | End time of the task execution | DATETIME | True | None | False |
| `error` | Error message, if any, associated with the task | VARCHAR | True | None | False |
| `created_at` | Date and time of creation | DATETIME | True | None | False |
| `updated_at` | Date and time of last update | DATETIME | True | None | False |
