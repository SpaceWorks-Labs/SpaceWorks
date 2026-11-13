---
title: Pagination and filtering
group: API
order: 30
summary: Page-number lists of 24, cursor reads for integrations, and the common query parameters.
---

# Pagination and filtering

## Page-number lists (the default)

List routes use DRF's `PageNumberPagination` with **24 rows per page**:

```json
{
  "count": 133,
  "next": "https://spaces.example.org/api/v1/admin/...?page=3",
  "previous": "https://spaces.example.org/api/v1/admin/...?page=1",
  "results": [ ]
}
```

- Ask for a page with `?page=2`. `next` and `previous` are full URLs, or `null` at the ends.
- Follow `next` until it is `null`; do not compute page numbers from `count`.
- Some staff lists (inventory products, machines, event and booking detail lists) also accept `?page_size=`, with a server-side maximum. Lists that do not accept it ignore it.

## Cursor reads (signed integrations)

The signed integration reads under `/api/v1/events/` and `/api/v1/booking-integration/` answer `{"next_cursor": string|null, "results": [...]}`.

- Pass `?cursor=` back **unchanged**, and `?page_size=` from 1 to 200 (default 100).
- Cursors are signed, expire after 24 hours and bind the client, tenant, subject and field projection; changing scopes cannot reuse an older cursor.
- Rows are in ascending ID order, so inserts never repeat earlier rows. This is live pagination, not a frozen snapshot.
- Responses are private and no-store.

## Filtering, search and ordering

Staff lists share a small vocabulary where the route supports it:

| Parameter | Meaning |
| --- | --- |
| `q` | Search within the list you are allowed to see |
| `ordering` | An allow-listed sort field; prefix with `-` for descending. An unsupported field answers `400` with `{"ordering": [...]}` |
| `id` | Select one result inside the authorized list |
| A named filter such as `status` | An unsupported value answers `400` naming the parameter |

The accepted parameters for each route are in its OpenAPI entry at `/docs/`. Ordering is always made stable by a final sort on the primary key, so pages do not overlap.

> **Tip** Filters narrow what you are already allowed to see. They never widen it: a list is scoped by your roles and space before any parameter applies.

## See also

- [Errors](errors.md)
- [API overview](overview.md)
