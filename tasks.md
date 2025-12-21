# Tasks: Simplify BitrixTask to camelCase

## Goal
Remove `AliasChoices` and use camelCase field names only, matching the actual Bitrix24 API response format.

## Tasks

- [x] Update `types.py` to use camelCase only (remove AliasChoices)
- [x] Update test fixtures in `conftest.py` to use camelCase
- [x] Update `test_client.py` mock responses to use camelCase
- [x] Update `test_integration.py` mock responses to use camelCase  
- [x] Update `test_tools.py` mock responses to use camelCase
- [x] Run tests to verify all pass (32/32 passed ✓)

## API Response Format (reference)

The Bitrix24 API returns tasks in camelCase:

```json
{
  "id": "836",
  "title": "Task title",
  "description": "Task description",
  "responsibleId": "22",
  "groupId": "5",
  "parentId": null,
  "status": "5",
  "priority": "1",
  "deadline": null,
  "createdBy": "1"
}
```

## Summary of Changes

### `types.py`
- Removed `AliasChoices` import
- Changed field definitions to use simple `alias` for camelCase mapping
- Cleaner, simpler model that matches actual API responses

### Test files
- Updated all mock responses from UPPERCASE to camelCase format
- All 32 tests passing
