# Domain Model Separation Pattern

## Overview

This document describes the three-layer model separation pattern implemented in whisperX-FastAPI to maintain clean architecture boundaries and enable independent evolution of different layers.

## Architecture Layers

### 1. API Layer (DTOs - Data Transfer Objects)

**Location:** `app/api/schemas/`

**Purpose:** Define request and response contracts for the REST API.

**Technology:** Pydantic models with validation

**Example:**

```python
from pydantic import BaseModel, Field

class TaskResponse(BaseModel):
    """DTO for returning full task details via API."""
    identifier: str = Field(..., description="Unique identifier for the task")
    status: str = Field(..., description="Current status of the task")
    task_type: str = Field(..., description="Type of task")
    # ... other fields
```

**Characteristics:**

- Contains Pydantic validation rules
- Defines API contracts (what clients see)
- Separate DTOs for different operations (Create, Update, Response)
- Can change independently from domain logic

### 2. Domain Layer (Entities)

**Location:** `app/domain/entities/`

**Purpose:** Represent business entities with business logic and validation rules.

**Technology:** Pure Python dataclasses (no framework dependencies)

**Example:**

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Task:
    """Domain entity representing a processing task."""
    uuid: str
    status: str
    task_type: str
    # ... other fields

    def mark_as_completed(self, result: dict, duration: float) -> None:
        """Business logic for completing a task."""
        if self.status != "processing":
            raise ValueError("Cannot complete task that's not processing")
        self.status = "completed"
        self.result = result
        self.duration = duration
        self.end_time = datetime.utcnow()
```

**Characteristics:**

- Pure Python (no Pydantic, no SQLAlchemy)
- Contains business logic methods
- Enforces business rules
- Framework-independent

### 3. Infrastructure Layer (ORM Models)

**Location:** `app/infrastructure/database/models.py`

**Purpose:** Define database schema and persistence concerns.

**Technology:** SQLAlchemy ORM models

**Example:**

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Task(Base):
    """ORM model for task persistence."""
    __tablename__ = "tasks"

    uuid: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    task_type: Mapped[str] = mapped_column(String)
    # ... other columns
```

**Characteristics:**

- SQLAlchemy-specific annotations
- Database schema definition
- Persistence concerns only
- No business logic

## Mapper Pattern

Mappers convert between different model types, maintaining separation of concerns.

### API Mappers

**Location:** `app/api/mappers/`

**Purpose:** Convert between API DTOs and domain entities.

**Example:**

```python
class TaskMapper:
    @staticmethod
    def to_domain(dto: CreateTaskRequest, uuid: str) -> Task:
        """Convert API DTO to domain entity."""
        return Task(
            uuid=uuid,
            status="processing",
            task_type=dto.task_type,
            # ... map other fields
        )

    @staticmethod
    def to_response(entity: Task) -> TaskResponse:
        """Convert domain entity to API response DTO."""
        return TaskResponse(
            identifier=entity.uuid,
            status=entity.status,
            task_type=entity.task_type,
            # ... map other fields
        )
```

### Database Mappers

**Location:** `app/infrastructure/database/mappers/`

**Purpose:** Convert between domain entities and ORM models.

**Example:**

```python
def to_domain(orm_task: ORMTask) -> DomainTask:
    """Convert ORM model to domain entity."""
    return DomainTask(
        uuid=orm_task.uuid,
        status=orm_task.status,
        # ... map other fields
    )

def to_orm(domain_task: DomainTask) -> ORMTask:
    """Convert domain entity to ORM model."""
    return ORMTask(
        uuid=domain_task.uuid,
        status=domain_task.status,
        # ... map other fields
    )
```

## Data Flow

```text
┌─────────────────────────────────────────────────────────────────┐
│                         API Request (JSON)                       │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│              API DTO (Pydantic - Request Validation)             │
│                  app/api/schemas/task_schemas.py                 │
└─────────────────────────────────────────────────────────────────┘
                                 │
                          [API Mapper]
                   app/api/mappers/task_mapper.py
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│       Domain Entity (Pure Python - Business Logic)               │
│                app/domain/entities/task.py                       │
│                                                                  │
│  Methods:                                                        │
│  - mark_as_completed(result, duration)                          │
│  - mark_as_failed(error)                                        │
│  - is_processing()                                              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                        [Service Layer]
                   app/services/*.py
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│          Domain Entity (modified by business logic)              │
└─────────────────────────────────────────────────────────────────┘
                                 │
                        [Database Mapper]
            app/infrastructure/database/mappers/task_mapper.py
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│         ORM Model (SQLAlchemy - Persistence)                     │
│           app/infrastructure/database/models.py                  │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Database                                │
└─────────────────────────────────────────────────────────────────┘
```

## Benefits

### 1. Business Logic Centralization

- All business rules live in domain entities
- Easy to find and modify business logic
- No duplication across layers

### 2. Independent Evolution

- Change API without changing domain logic
- Change database schema without changing business rules
- Refactor one layer without affecting others

### 3. Framework Independence

- Domain layer has no FastAPI/SQLAlchemy dependencies
- Can switch frameworks without rewriting business logic
- Easier to test business logic in isolation

### 4. Better Testing

- Test business logic without web framework
- Test API contracts separately
- Mock dependencies easily

### 5. Clear Contracts

- API DTOs define clear input/output contracts
- Domain entities define business behavior
- ORM models define persistence structure

### 6. Type Safety

- Each layer has appropriate types for its concerns
- Type checking catches cross-layer violations
- Better IDE support and autocomplete

## Usage Examples

### In API Routers

```python
from app.api.mappers.task_mapper import TaskMapper
from app.api.schemas.task_schemas import TaskListResponse

@router.get("/task/all")
async def get_all_tasks(
    service: TaskManagementService = Depends(get_task_management_service),
) -> TaskListResponse:
    # Get domain entities from service
    tasks = service.get_all_tasks()

    # Convert to API DTOs using mapper
    task_summaries = [TaskMapper.to_summary(task) for task in tasks]

    return TaskListResponse(tasks=task_summaries)
```

### In Services

```python
from app.domain.entities.task import Task

class TaskManagementService:
    def get_task(self, identifier: str) -> Task | None:
        """Service works with domain entities only."""
        return self.repository.get_by_id(identifier)
```

### In Repositories

```python
from app.infrastructure.database.mappers.task_mapper import to_domain, to_orm

class SQLAlchemyTaskRepository:
    def get_by_id(self, identifier: str) -> Task | None:
        orm_task = self.session.query(ORMTask).filter(...).first()
        if orm_task:
            return to_domain(orm_task)  # Convert to domain entity
        return None

    def add(self, task: Task) -> str:
        orm_task = to_orm(task)  # Convert to ORM model
        self.session.add(orm_task)
        self.session.commit()
        return orm_task.uuid
```

## Implementation Checklist

When implementing model separation for a new entity:

- [ ] Create domain entity in `app/domain/entities/`
  - [ ] Use dataclass
  - [ ] Add business logic methods
  - [ ] Add validation methods
  - [ ] No framework dependencies

- [ ] Create API DTOs in `app/api/schemas/`
  - [ ] Define CreateRequest DTO
  - [ ] Define Response DTO
  - [ ] Define Summary DTO (for lists)
  - [ ] Add Pydantic validation

- [ ] Create API mapper in `app/api/mappers/`
  - [ ] Implement `to_domain()` function
  - [ ] Implement `to_response()` function
  - [ ] Implement `to_summary()` function

- [ ] Create database mapper in `app/infrastructure/database/mappers/`
  - [ ] Implement `to_domain()` function
  - [ ] Implement `to_orm()` function
  - [ ] Handle JSON serialization
  - [ ] Handle datetime conversions

- [ ] Update repository
  - [ ] Use database mapper for conversions
  - [ ] Work with domain entities

- [ ] Update service
  - [ ] Work with domain entities only
  - [ ] No Pydantic or SQLAlchemy types

- [ ] Update routers
  - [ ] Use API DTOs for request/response
  - [ ] Use API mapper for conversions
  - [ ] Call service with domain entities

- [ ] Add tests
  - [ ] Test domain entity business logic
  - [ ] Test API mapper conversions
  - [ ] Test database mapper conversions
  - [ ] Test round-trip conversions

## References

- **Domain-Driven Design** by Eric Evans
- **Clean Architecture** by Robert C. Martin
- **Repository Pattern**: <https://martinfowler.com/eaaCatalog/repository.html>
- **DTO Pattern**: <https://martinfowler.com/eaaCatalog/dataTransferObject.html>
