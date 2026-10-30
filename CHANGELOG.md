# Changelog

## 2.1.1

No behaviour changes; documentation and comments only.

### Documentation
- Documented how regions and failover work: the client uses the global Health
  endpoint (DNS failover between us-east-1 and us-east-2), there is no
  client-side failover, passive data can lag, and signing after a real failover
  is unverified. Corrects the earlier "only available through us-east-1" wording.

## 2.1.0

### Added
- Seven read-only tools (11 -> 18): `get_event_details`, `summarize_health_events`,
  `count_affected_entities`, `list_affected_accounts`, `list_event_types`,
  `check_health_access`, `find_events_for_resources`.
- `regions` filter on the listing tools.
- CI runs weekly and starts the server over stdio to check it registers its tools.

### Changed
- **Errors are now MCP tool errors** (`isError`) instead of plain strings that
  read like normal results. Clients matching on the old `"Error fetching ..."`
  text in successful results should check `isError` instead.
- Failed lookups inside a larger answer produce a "partial results" warning
  instead of being silently dropped. Searches that could not check every event
  return an error rather than "nothing found".
- Service names are resolved against the live Health API (322 services) instead
  of a stale hardcoded list of 83 that rejected real services and accepted
  wrong ones.
- Cached event descriptions are keyed on the event's `lastUpdatedTime`, so an
  ongoing event no longer shows an outdated update.
- Server-side account filtering for organization queries (one call instead of
  one per event).
- Requires `mcp>=1.22.0` (older versions fail to import against current
  `pydantic`).

### Fixed
- First service query took ~68 seconds on a cold start; common names now resolve
  in about a second.
- A failed affected-accounts lookup was cached as "no accounts".

### Removed
- The `AWS_REGION` setting, which never had any effect (the Health API client is
  fixed to `us-east-1`).
- Unused modules `models.py`, `errors.py` and `debug_helper.py`.
