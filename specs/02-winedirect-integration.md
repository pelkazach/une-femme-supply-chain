# Spec: WineDirect API Integration

## Job to Be Done
As a supply chain operator, I need to automatically pull depletion and inventory data from WineDirect so that I have real-time visibility into distributor inventory levels and sales velocity without manual data entry.

## Requirements
- Obtain ANWD REST API credentials from Jeff Carroll (jeff.carroll@winedirect.com)
- Implement Bearer Token authentication via AccessToken endpoint
- Create API client for inventory endpoints (GET sellable, inventory-out tracking)
- Pull Inventory Velocity reports (30/60/90-day lookback)
- Store retrieved data in Supabase inventory_events table
- Schedule daily batch sync (aligned with WineDirect Data Lake refresh)
- Handle HTTPS requirement (mandatory after Feb 16, 2026)

## Acceptance Criteria
- [ ] WineDirect API client successfully authenticates with Bearer Token
- [ ] GET /inventory/sellable returns current inventory positions
- [ ] GET /inventory-out returns depletion events
- [ ] Velocity reports parsed into 30/60/90-day depletion rates
- [ ] Data correctly inserted into inventory_events hypertable
- [ ] Daily sync job runs without manual intervention
- [ ] All API calls use HTTPS

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| Valid credentials | Bearer token returned, stored securely |
| GET /inventory/sellable | JSON with SKU, quantity, pool data |
| Invalid token | 401 error, token refresh triggered |
| Parse velocity report | Depletion rate in units/day extracted |
| Sync job trigger | New inventory_events rows created |

## Technical Notes
- ANWD REST APIs are modern, wine-specific endpoints
- Authentication: Bearer Token via AccessToken endpoint
- Data Lake refresh: ANWD hourly, Classic daily
- Rate limits: Not explicitly documented, implement exponential backoff
- Critical deadline: HTTPS-only after February 16, 2026

## API Client Structure

```python
# winedirect_client.py
class WineDirectClient:
    BASE_URL = "https://api.winedirect.com/v1"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expires = None

    async def authenticate(self) -> str:
        """Get Bearer token from AccessToken endpoint"""
        pass

    async def get_sellable_inventory(self) -> list[dict]:
        """Fetch current sellable inventory positions"""
        pass

    async def get_inventory_out(self, since: datetime) -> list[dict]:
        """Fetch depletion events since timestamp"""
        pass

    async def get_velocity_report(self, days: int) -> dict:
        """Get 30/60/90-day velocity report"""
        pass
```

## Source Reference
- [[winedirect-api]] - Complete API documentation and authentication patterns
- [[ekos-vip-integration]] - Similar integration pattern with daily batch sync
