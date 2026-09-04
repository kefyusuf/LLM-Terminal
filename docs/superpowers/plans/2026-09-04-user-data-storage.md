# User data storage fix

## Scope

- store runtime SQLite data in the OS-appropriate per-user data directory
- keep explicit environment overrides working
- copy legacy source-tree databases only when the new target does not exist
- never delete or overwrite legacy data during migration
- validate wheel/source behavior through existing CI
