# Scrum Backlog Tasks MCP Implementation Plan

## 1. Goal

Implement a new MCP tool that returns **all tasks currently in the backlog** for a given Scrum
group.

Primary user outcome:
- Provide `groupId`
- Get backlog metadata and the full list of backlog task cards in one call

---

## 2. Scope

### In scope

1. New tool: `scrum_backlog_tasks(groupId: int) -> dict`
2. Client support for:
   - `tasks.api.scrum.backlog.get`
   - paginated `tasks.task.list` retrieval for backlog filters
3. Tests:
   - `tests/test_client.py`
   - `tests/test_tools.py`
   - `tests/test_integration.py` (workflow-level happy path)
4. README documentation update for the new tool

### Out of scope

1. Backlog mutation (add/update/delete backlog)
2. Sprint filtering or sprint-specific tool in this task
3. New prompt/resource definitions (tools-only server)

---

## 3. Tool Contract (Proposed)

### Tool name

`scrum_backlog_tasks`

### Parameters

- `groupId` (int, required): Scrum group/workgroup id

### Response shape

```json
{
  "groupId": 205,
  "backlogId": 1,
  "count": 2,
  "tasks": [
    {
      "id": 456,
      "title": "Auto Send welcome email",
      "responsibleId": 7,
      "groupId": 205,
      "parentId": null,
      "status": "pending",
      "url": "https://.../company/personal/user/7/tasks/task/view/456/"
    }
  ]
}
```

Notes:
- `tasks` format should reuse existing task normalization (`BitrixTask.to_search_result`).
- `status` remains the existing normalized string mapping used elsewhere in this server.

---

## 4. Implementation Design

### 4.1 Types layer (`src/bitrix_mcp/bitrix/types.py`)

Add a new model:
- `BitrixScrumBacklog`
  - `id`
  - `groupId`
  - `createdBy`
  - `modifiedBy`
  - `to_result()`

Reason:
- Keep backlog payload parsing typed and consistent with current Scrum models.

### 4.2 Client layer (`src/bitrix_mcp/bitrix/client.py`)

Add:

1. `scrum_backlog_get(self, group_id: int) -> BitrixScrumBacklog`
   - Call: `tasks.api.scrum.backlog.get`
   - Payload: `{"id": group_id}`
   - Validate response is dict-like
   - Raise `BitrixAPIError` on invalid format

2. A paginated task list reader for `tasks.task.list` with access to `next`:
   - Option A (preferred): new internal helper returning `{tasks, next, total}`
   - Option B: extend existing `task_list` with pagination metadata return
   - Plan chooses Option A to avoid changing behavior of existing callers

Pagination approach:
- Filter by:
  - `GROUP_ID = group_id`
  - `BACKLOG_ID = backlog_id`
- Loop until `next` is absent
- Collect tasks across pages

### 4.3 Server layer (`src/bitrix_mcp/server.py`)

Add:

1. Internal handler:
   - `_scrum_backlog_tasks(groupId: int) -> dict[str, Any]`
   - Flow:
     1. `backlog = client.scrum_backlog_get(group_id=groupId)`
     2. fetch paginated `tasks.task.list` with `BACKLOG_ID=backlog.id`
     3. map tasks via `to_search_result(base_url)`
     4. return `groupId`, `backlogId`, `count`, `tasks`

2. Public MCP tool wrapper:
   - `@mcp.tool async def scrum_backlog_tasks(groupId: int) -> dict[str, Any]`

Error mapping:
- Keep existing conventions:
  - `BitrixConnectionError` -> `RuntimeError("Failed to connect to Bitrix24: ...")`
  - `BitrixAPIError` -> `RuntimeError("Bitrix24 API error: ...")`

---

## 5. Testing Plan (Write tests during implementation)

### 5.1 Fixtures (`tests/conftest.py`)

Add fixtures:
1. `sample_scrum_backlog_get_response`
2. `sample_task_list_backlog_page_1_response` (`next=50`)
3. `sample_task_list_backlog_page_2_response` (no `next`)

All fixture keys must match real API formats (camelCase for task payload, per current tests).

### 5.2 Client tests (`tests/test_client.py`)

Add test class for `scrum_backlog_get`:
1. success parsing
2. request body validation (`id == group_id`)
3. unexpected response format raises `BitrixAPIError`

Add tests for paginated task reader used by backlog tool:
1. parses tasks + next cursor
2. handles last page (no `next`)
3. validates unexpected shape

### 5.3 Tool tests (`tests/test_tools.py`)

Add test class for `_scrum_backlog_tasks`:
1. returns backlog metadata + combined tasks
2. multi-page aggregation works
3. request filters include `GROUP_ID` and `BACKLOG_ID`
4. empty backlog task list returns `count=0`, `tasks=[]`
5. connection error mapping
6. API error mapping

### 5.4 Integration test (`tests/test_integration.py`)

Add one workflow test:
1. backlog lookup (`tasks.api.scrum.backlog.get`)
2. paginated task list retrieval
3. final aggregated result shape

---

## 6. Documentation Plan

Update `README.md`:
1. Add `scrum_backlog_tasks` section with:
   - purpose
   - parameters
   - response fields
2. Mention that the tool internally:
   - resolves backlog id via `tasks.api.scrum.backlog.get`
   - fetches tasks via paginated `tasks.task.list` with `BACKLOG_ID`

---

## 7. Execution Sequence

1. Add/adjust fixtures for backlog and paginated task list
2. Add failing client tests
3. Implement client methods/helpers
4. Add failing tool tests
5. Implement `_scrum_backlog_tasks` and public tool wrapper
6. Add integration test
7. Update README
8. Run:
   - `ruff check --fix .`
   - `ruff format .`
   - `pytest -v`
9. Fix any failures until all checks pass

---

## 8. Risks and Mitigations

1. `tasks.task.list` pagination shape can vary by endpoint wrappers
   - Mitigation: use `_request_raw` for robust access to `result`, `next`, `total`
2. Backlog may exist but have zero tasks
   - Mitigation: explicit empty-list handling and tests
3. Large backlogs can trigger multiple API calls
   - Mitigation: deterministic pagination loop and clear termination on missing `next`

---

## 9. Definition of Done

1. New tool `scrum_backlog_tasks` is available and returns all backlog tasks for a Scrum group
2. Unit tests for client/tool behavior pass
3. Integration workflow test passes
4. README documents usage and behavior
5. `ruff check --fix .`, `ruff format .`, and `pytest -v` all pass
