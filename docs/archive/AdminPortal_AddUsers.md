# Admin Portal → Database Flow

## The Short Version

Users added via Admin Portal write directly to `enterprise.users` table. Department access is stored as an array on the user row.

## Schema (2-Table Design)

```
enterprise.tenants     → Company/org info
enterprise.users       → All users + their department access
```

No separate join table. Access is an array column:

```sql
department_access TEXT[]  -- e.g. {'warehouse', 'sales', 'credit'}
```

## Write Path

```
Admin Portal UI
    ↓
POST /api/admin/users/batch
    ↓
auth_service.get_or_create_user()
    ↓
INSERT INTO enterprise.users
    ↓
auth_service.grant_department_access()
    ↓
UPDATE users SET department_access = array_append(...)
```

## Verify It Worked

```sql
-- Check user was created
SELECT email, department_access, created_at
FROM enterprise.users
WHERE email = 'someone@driscollfoods.com';

-- Check department access granted
SELECT email FROM enterprise.users
WHERE 'warehouse' = ANY(department_access);
```

## Key Files

| File | Purpose |
|------|---------|
| `admin_routes.py:1026` | Batch endpoint |
| `auth_service.py:288` | User creation |
| `auth_service.py:640` | Access grant |
