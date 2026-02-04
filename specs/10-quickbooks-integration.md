# Spec: QuickBooks Online Integration

## Job to Be Done
As a finance director, I need inventory and sales data synced with QuickBooks Online so that financial reporting reflects current inventory positions and revenue recognition is accurate without duplicate data entry.

## Requirements
- Authenticate with QuickBooks Online via OAuth 2.0
- Sync inventory levels bidirectionally
- Pull invoice and payment data for AR tracking
- Push sales data for revenue recognition
- Handle OAuth token refresh automatically
- Support sandbox testing before production
- Respect API rate limits (500 req/min)

## Acceptance Criteria
- [ ] OAuth 2.0 flow completes successfully
- [ ] Inventory quantities match between systems (±1%)
- [ ] Invoice data pulled from QuickBooks
- [ ] Sales data pushed to QuickBooks
- [ ] Token refresh happens automatically before expiry
- [ ] Sync completes within 15 minutes of trigger
- [ ] Rate limiting handled gracefully

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| OAuth authorization code | Access + refresh tokens stored |
| Sync trigger (inventory update) | QBO inventory updated |
| Token near expiry | Automatic refresh, no user action |
| Rate limit hit | Backoff and retry, sync completes |
| Mismatched inventory | Discrepancy flagged for review |

## Technical Notes
- Use python-quickbooks library for API interaction
- OAuth tokens: 1-hour access, 24-hour refresh
- Rate limits: 500 req/min, 10 concurrent connections
- Sandbox environment for testing (sandbox.quickbooks.intuit.com)
- Optimize for write-heavy patterns (new QBO pricing model)

## Integration Architecture

```python
from quickbooks import QuickBooks
from quickbooks.objects import Item, Invoice
from intuitlib.client import AuthClient

class QuickBooksIntegration:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.auth_client = AuthClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            environment='production'  # or 'sandbox'
        )
        self.qb_client = None

    def get_authorization_url(self) -> str:
        """Generate OAuth authorization URL for user consent"""
        return self.auth_client.get_authorization_url(
            scopes=['com.intuit.quickbooks.accounting']
        )

    async def exchange_code(self, auth_code: str) -> dict:
        """Exchange authorization code for tokens"""
        self.auth_client.get_bearer_token(auth_code)
        return {
            'access_token': self.auth_client.access_token,
            'refresh_token': self.auth_client.refresh_token,
            'realm_id': self.auth_client.realm_id
        }

    async def refresh_tokens(self) -> None:
        """Refresh access token before expiry"""
        self.auth_client.refresh()

    async def sync_inventory(self, products: list[dict]) -> dict:
        """Sync inventory quantities to QuickBooks"""
        results = {'success': 0, 'failed': 0, 'errors': []}

        for product in products:
            try:
                item = Item.filter(
                    Name=product['sku'],
                    qb=self.qb_client
                )[0]
                item.QtyOnHand = product['quantity']
                item.save(qb=self.qb_client)
                results['success'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'sku': product['sku'],
                    'error': str(e)
                })

        return results

    async def get_invoices(self, since: datetime) -> list[dict]:
        """Pull invoices from QuickBooks"""
        invoices = Invoice.filter(
            MetaData_LastUpdatedTime=f">{since.isoformat()}",
            qb=self.qb_client
        )
        return [inv.to_dict() for inv in invoices]
```

## Sync Schedule

| Sync Type | Frequency | Direction |
|-----------|-----------|-----------|
| Inventory levels | Every 4 hours | Bidirectional |
| Invoices | Daily | QBO → Platform |
| Payments | Daily | QBO → Platform |
| Sales orders | On creation | Platform → QBO |

## Error Handling

| Error | Action |
|-------|--------|
| 401 Unauthorized | Refresh token, retry |
| 429 Rate Limit | Exponential backoff |
| 500 Server Error | Retry 3x with delay |
| Validation Error | Log, flag for review |

## Source Reference
- [[quickbooks-api]] - API documentation and OAuth patterns
- Research synthesis: "QuickBooks Online Integration" section
