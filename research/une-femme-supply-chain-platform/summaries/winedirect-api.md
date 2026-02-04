# WineDirect API Comprehensive Analysis

## Executive Summary

WineDirect offers a comprehensive suite of APIs and webservices designed to enable wine commerce businesses to integrate order management, inventory tracking, and fulfillment operations. The platform supports three integration pathways: modern All-New WineDirect (ANWD) REST APIs with wine-specific functionality, legacy Classic WineDirect SOAP APIs, and specialized WineDirect Fulfillment APIs. For supply chain intelligence purposes, the ANWD REST APIs combined with the Fulfillment API and Data Lake provide real-time inventory visibility, depletion tracking across multiple inventory pools, and comprehensive order management capabilities. A critical February 16, 2026 HTTPS-only migration deadline requires immediate attention for any integrations.

## Key Concepts & Definitions

**All-New WineDirect (ANWD)**: Modern REST API ecosystem providing real-time, wine-specific functionality beyond standard e-commerce capabilities. Requires direct contact with VP Partnerships Compliance.

**Classic WineDirect**: Legacy SOAP-based integration pathway with deprecation planned; uses Version 1, 2, and 3 webservices.

**WineDirect Fulfillment API**: Specialized REST API for fulfillment operations across four states (Tier 3-licensed), handling order processing, inventory transfers, and warehouse management.

**Inventory Pools**: Segmentation mechanism allowing wineries to differentiate inventory by operational channel (website, POS, wine club, manual orders). Website orders exclusively use the default pool.

**Bearer Token Authentication**: Token-based security model requiring AccessToken endpoint call to obtain authorization header for all subsequent API calls.

**Data Lake**: Hourly-refreshed warehouse of ANWD order, customer, product, and wine club data; daily updates from Classic systems. Supports historical analysis and comprehensive reporting.

## Main API Capabilities & Integration Architecture

### Three Distinct Integration Pathways

**1. All-New WineDirect (ANWD) REST APIs**
- Purpose: "Purpose-built APIs complement the BigCommerce APIs to provide real-time, wine-specific functionality via RESTful APIs"
- Architecture: RESTful with wine-specific endpoints
- Access: Requires contacting Jeff Carroll, VP of Partnerships Compliance (jeff.carroll@winedirect.com)
- Documentation: Available via [ANWD Swagger endpoint](https://swagger.api.winedirect.com/?urls.primaryName=WineDirect%20API)
- Key advantage: Real-time wine-specific functionality unavailable in standard e-commerce platforms
- Data sync: All ANWD stores automatically synchronize order, product, customer, and inventory data to BigCommerce

**2. Classic WineDirect SOAP APIs**
- Versions: 1 (deprecated), 2, and 3
- Status: Deprecation planned; legacy pathway
- Authentication: Username/password credentials in all requests
- Timezone handling: Version 2.0 uses Pacific Standard Time; Version 3+ uses UTC
- Regional variations: Australian clients use different endpoints
- Maintenance window: Daily 8am EST/5am PST (US/Canada); 11pm AWST/1am AEST (Australia/New Zealand)

**3. WineDirect Fulfillment API**
- Scope: Specialized fulfillment operations across four states
- Base: https://docs.winedirectfulfillment.com/
- Version: 1.0
- Contact: csoperations@winedirect.com
- Authentication: Bearer Token via AccessToken endpoint

### Authentication Methods

**Bearer Token Authentication (Fulfillment API)**
- Step 1: Call AccessToken endpoint to obtain Bearer token
- Step 2: Include token as HttpHeader named "Authorization" on all subsequent requests
- Implementation: Supported in browser via Authorize button or programmatically (C# examples provided)

**Basic Authentication (Classic APIs)**
- All requests include username and password credentials directly
- Each API call validates credentials

**BigCommerce Integration Path**
- Store-level API accounts follow BigCommerce authentication protocols
- Alternative pathway leveraging BigCommerce marketplace integration

### Available Endpoints & Capabilities

**Order Management Endpoints**
- GET: Retrieve single order by order number
- GET: Retrieve multiple orders (batch retrieval)
- GET: Orders on hold status
- POST: Update existing order
- POST: Update orders in bulk
- POST: Upload many orders in batch to processing queue (15-minute processing time)
- DELETE: Cancel/delete existing order
- GET: Retrieve order status

**Inventory Management Endpoints**
- GET: List of sellable inventory (inventory items with availability)
- GET: Inventory-out order list (fulfillment system inventory deductions)
- GET: Specific inventory-out details
- POST: Create inventory OUT request (depletion record)
- POST: Submit inventory OUT (finalize depletion)
- DELETE: Cancel specific inventory-outs
- POST: Create inter-warehouse transfers

**Warehouse & Fulfillment Endpoints**
- GET: List of warehouses and subinventories for specified customers
- POST: Create inventory movement requests

### Response Format & Data Structure

**GET Response Structure** (success pattern)
- Success flag (boolean indicating operation result)
- Record count (number of items returned)
- Error messages (if applicable; null on success)
- Object collections (array of requested entities)

**Upsert Response Structure** (for POST operations)
- Success indicator per object (granular result for each record in batch)
- External key code (system identifier in calling system)
- Internal key code (Vin65 system ID for matching records)
- Error messages (per-record validation errors if applicable)

**OpenAPI Documentation**: Complete specification available via Swagger download from Fulfillment API documentation

### Rate Limiting & Performance Controls

**Implementation**: Effective October 26, 2022, rate limits were implemented to prevent large dataset errors and enhance platform performance.

**Effect on large data operations**: Rate limits prevent timeout issues when retrieving large datasets; batch uploads (e.g., orders) are queued and processed asynchronously (15-minute processing window typical).

**Best practice**: Use batch endpoints for bulk operations rather than individual API calls; leverage Data Lake for historical/reporting data access.

## Inventory & Depletion Tracking Capabilities

### Inventory Pool Architecture

**Pool Segmentation Model**: Inventory organized by operational channel
- **Default pool**: Exclusive source for website/e-commerce orders (fundamental constraint)
- **POS pools**: Can be assigned per location or iPad workstation
- **Wine club pools**: Dedicated inventory for club fulfillment
- **Admin/manual order pools**: Designated sources for administrative orders

**Pool Configuration Data Fields**:
- Pool name (special characters avoided for import compatibility)
- Default status designation
- Out-of-stock behavior (deactivate products | backorder with messaging | hide while displaying)
- Low-inventory thresholds (email alert triggers, website quantity displays)
- Display settings (show remaining units after threshold)

**Depletion Tracking**: System tracks which pool was depleted through order references and inventory transaction reports, enabling operational visibility across multiple locations.

### Inventory Reporting & Depletion Analysis

**Four Primary Inventory Reports**:

1. **Inventory Summary Report**
   - Data: Current inventory amount per product, notification level, out-of-stock message
   - Purpose: Overview of inventory status and alert thresholds

2. **Inventory Transactions Report**
   - Data: Starting balance → increases/decreases → ending balance
   - Scope: Configurable date range selection
   - Use case: Granular movement tracking for reconciliation

3. **Inventory Velocity Report**
   - Analysis periods: 30, 60, and 90-day lookback windows
   - Key metric: "Approximates the rate you will deplete your remaining inventory"
   - Guidance: Assessment of whether inventory levels are adequate or require replenishment
   - Supply chain value: Predictive depletion forecasting based on historical velocity

4. **Inventory Sold Report**
   - Data: Inventory breakdown across different pools alongside associated sales
   - Timeframe: Configurable date ranges
   - Use case: Pool-specific sales impact analysis

**Report Access**: Currently available through WineDirect platform UI; programmatic API access details not fully documented in available sources (may require developer contact).

## Data Lake for Historical & Reporting Access

**Architecture**: Centralized data warehouse with tiered refresh schedules

**Refresh Cadence**:
- ANWD data: Hourly refresh (orders, customers, products, wine club information)
- Classic system data: Daily updates

**Key advantages**:
- Decoupled reporting from operational API load
- Historical data retention for trend analysis
- Supports complex queries without impact on transaction systems
- Enables batch analytics and BI tool integration

**Data entities available**: Orders, customers, products, wine club operations

## Technical Requirements & Constraints

### Critical Infrastructure Changes

**February 16, 2026 HTTPS-Only Migration**: Non-HTTPS API calls will receive HTTP 302 redirects. This will break integrations using HTTP (non-encrypted). Required action: Update all integrations to HTTPS before this date.

### Regional & Timezone Considerations

**Timezone variance**: Version 2.0 APIs use Pacific Standard Time (PST); Version 3+ use UTC. This affects timestamp interpretation for order/inventory timestamp fields.

**Regional endpoints**: Australian clients use different API endpoints than North American clients; endpoint routing differs by region.

**Maintenance windows**: Planned daily downtime affects integration scheduling:
- US/Canada: 8am EST / 5am PST
- Australia/New Zealand: 11pm AWST / 1am AEST

### Setup & Admin Requirements

**Prerequisites for API access**: "An admin of the website must set up the account and agree to the terms of use" through the WineDirect admin panel. This administrative approval is mandatory before API credentials can be issued.

## Integration Patterns & Recommendations for Supply Chain Intelligence

### Recommended Architecture for Une Femme Supply Chain Platform

**Multi-layer integration approach**:

1. **Real-time order synchronization** via ANWD REST APIs
   - Endpoint: GET multiple orders with filters
   - Frequency: Periodic polling (rate-limit aware) or webhook-based (if available)
   - Purpose: Keep order status and channel information current

2. **Inventory pool depletion tracking** via Fulfillment API
   - Endpoint: GET inventory-out order list, GET specific inventory-out details
   - Frequency: Real-time or hourly refresh
   - Purpose: Track actual depletion events across inventory pools
   - Data fields: Pool identifier, depletion quantity, timestamp, order reference

3. **Predictive analysis via Inventory Velocity reports**
   - Source: 30/60/90-day inventory velocity reports
   - Frequency: Daily aggregation
   - Purpose: Forecast depletion timeline based on historical velocity
   - Use case: Supply chain replenishment decision support

4. **Historical analysis via Data Lake**
   - Source: WineDirect Data Lake (hourly ANWD data, daily Classic data)
   - Frequency: Batch queries for trend analysis
   - Purpose: Long-term depletion patterns, seasonality analysis, demand forecasting

### Authentication & Security Implementation

**For ANWD REST APIs**:
- Contact: Jeff Carroll (jeff.carroll@winedirect.com)
- Flow: Obtain API credentials, implement Bearer Token pattern
- Security: HTTPS-only from February 16, 2026 onward

**For Fulfillment API**:
- Contact: csoperations@winedirect.com
- Flow: Call AccessToken endpoint → store Bearer token → include in Authorization header
- Security: Token-based, HTTPS-only

**Credential management**: Store API credentials securely (environment variables or secrets manager); never hardcode credentials in application code.

### Data Synchronization Strategy

**Recommended approach**:
- **Initial load**: Batch retrieve all orders and inventory data via high-volume endpoints
- **Ongoing sync**:
  - Orders: Periodic poll for new/updated orders (filter by date range)
  - Inventory: Monitor inventory-out endpoints for depletion events
  - Velocity: Daily refresh of predictive metrics
- **Error handling**: Implement retry logic with exponential backoff for rate-limited responses
- **Data validation**: Cross-reference order depletion with inventory pool records

### Batch Processing Considerations

**Order batch uploads**: 15-minute processing window typical
- Use for bulk order imports from external systems
- Not suitable for real-time order creation
- Response includes per-record success/error status

**Inventory transfers**: Asynchronous processing
- Create request → submit request → monitor status
- Not immediate; plan for delay in visibility

### BigCommerce Integration Option

**Alternative pathway**: If Une Femme operates BigCommerce storefronts:
- Automatic order/product/customer sync to BigCommerce
- Leverage BigCommerce marketplace integrations
- Developer account setup: developer.bigcommerce.com
- Wine-specific ANWD APIs still required for depletion/inventory pool intelligence

## Evidence & Supporting Data

### Official Documentation Sources

- **WineDirect APIs / Webservices Overview**: Primary reference for core API architecture, authentication patterns, and maintenance windows
- **WineDirect Integration Options**: Details on ANWD vs. Classic vs. Fulfillment pathways and contact information
- **WineDirect Fulfillment API Guide**: Bearer Token authentication, Swagger OpenAPI specification
- **Inventory Pools documentation**: Pool architecture and channel-specific depletion tracking
- **Inventory Reports documentation**: Four report types and data fields available
- **WineDirect Data Lake**: Hourly/daily refresh schedules for historical data access

### Key Quotes from Documentation

"Purpose-built APIs complement the BigCommerce APIs to provide real-time, wine-specific functionality via RESTful APIs." (ANWD architecture description)

"Having Inventory Pools is a tool for wineries to differentiate their products from a certain inventory section." (Inventory Pools definition)

"Website orders exclusively draw from the designated default pool." (Critical constraint for order routing)

"Approximates the rate you will deplete your remaining inventory" (Inventory Velocity Report capability)

"Non-HTTPS API calls will receive HTTP 302 redirects, potentially breaking incompatible integrations." (February 16, 2026 critical deadline)

## Critical Evaluation & Limitations

### Documentation Gaps

**Missing specifications**:
- Specific rate limit values (e.g., requests per minute/hour) not documented in available sources
- Detailed request parameter specifications for each endpoint (e.g., filter syntax, pagination)
- Exact field names and data types in response schemas (inferred from context)
- Webhook support for real-time notifications (not mentioned; may require direct inquiry)
- SLA guarantees for API availability or response times

**Programmatic access to reports**: Inventory reports (Velocity, Transactions, Sold) documented as UI-based; API access path unclear and may require custom development

**Depletion event granularity**: While inventory-out endpoints exist, specifics on timestamp precision, SKU-level detail, and channel attribution not fully detailed

### Reliability & Version Considerations

**Multiple API versions**: Support for Versions 1-3 suggests potential compatibility challenges during migration. Version selection strategy required.

**Deprecation timeline**: Classic APIs planned for deprecation without published timeline. Migration to ANWD required for long-term sustainability.

**Regional variations**: Australian endpoints differ from North American; global deployment requires region-specific configuration.

### Implementation Complexity

**Multi-pathway authentication**: Different approaches for ANWD (contact required), Classic (basic auth), and Fulfillment (Bearer Token) require flexible credential management.

**Pool-based inventory model**: Default pool constraint for website orders may limit cross-channel flexibility; requires careful pool configuration planning.

**Maintenance windows**: Daily planned downtime affects real-time update frequency; scheduling integration runs outside 8am EST window required.

## Relevance to Une Femme Supply Chain Intelligence Platform

### Direct Alignment with Platform Requirements

**Wine depletion data**:
- Inventory-out endpoints provide transaction-level depletion records
- Inventory pool tracking enables channel-specific depletion analysis
- Inventory Velocity reports offer predictive depletion forecasting
- Highest relevance: Enables core supply chain forecasting capability

**Inventory synchronization**:
- GET inventory endpoints provide real-time sellable inventory snapshot
- Fulfillment API supports inventory movement tracking
- Data Lake enables bulk historical inventory state reconstruction
- Moderate relevance: Supports inventory status reporting; real-time sync latency acceptable for most use cases

**Order management**:
- Comprehensive order CRUD operations
- Batch order processing for imports
- Order status tracking across channels
- Order-inventory linkage through transaction records
- Moderate relevance: Supports order fulfillment workflow integration

### Unique Wine Industry Capabilities

WineDirect's inventory pool architecture and velocity-based depletion forecasting are industry-specific strengths not available in generic e-commerce platforms. The depletion velocity reports provide wine business-specific predictive analytics that directly support the Una Femme platform's supply chain intelligence goal.

### Integration Complexity Assessment

**Moderate complexity**:
- Multiple authentication methods manageable with abstraction layer
- Well-documented endpoint patterns (REST)
- Batch processing suitable for supply chain workloads
- Established contact process for ANWD access

**Effort estimate**:
- Initial integration (single product): 2-3 weeks (authentication + order/inventory endpoints)
- Advanced features (depletion forecasting, pool analytics): 4-6 weeks
- Data Lake integration (historical analysis): 2-3 weeks
- Testing & optimization: 2-3 weeks

## Practical Implementation Considerations

### Prerequisites Before Integration

1. **Administrative setup**: WineDirect admin must approve API access and agree to terms
2. **ANWD contact**: Email Jeff Carroll (jeff.carroll@winedirect.com) with API requirements
3. **Fulfillment contact**: Email csoperations@winedirect.com if Tier 3 state fulfillment required
4. **HTTPS compliance**: Ensure all client infrastructure supports HTTPS (Feb 16, 2026 deadline)
5. **Environment setup**: Configure separate credentials for dev/test/production environments

### Development Workflow

1. **Phase 1 - Authentication**:
   - Implement Bearer Token acquisition and refresh logic
   - Test with Fulfillment API (publicly accessible)
   - Validate HTTPS-only requirement

2. **Phase 2 - Core endpoints**:
   - Orders: GET multiple, GET single, POST update
   - Inventory: GET sellable inventory, inventory-out tracking
   - Testing: Batch operations and filtering

3. **Phase 3 - Advanced features**:
   - Pool-based inventory analysis
   - Depletion velocity integration
   - Data Lake queries for historical analysis

4. **Phase 4 - Optimization**:
   - Rate limiting compliance verification
   - Batch processing tuning
   - Error handling and retry logic

### Monitoring & Maintenance

- Monitor February 16, 2026 HTTPS migration; test well before deadline
- Track API version usage; plan Classic → ANWD migration timeline
- Monitor depletion report data freshness (reconcile Velocity reports with actual inventory-out records)
- Set up alerts for inventory pool constraint violations (website orders from non-default pools)

## Conclusion

WineDirect provides a mature, wine-industry-specific API ecosystem well-suited for the Une Femme supply chain intelligence platform. The combination of real-time order and inventory endpoints, inventory pool architecture, and predictive depletion velocity reporting directly addresses the platform's core requirements. The February 16, 2026 HTTPS migration deadline requires immediate planning, and ANWD access requires direct contact with partnerships team. The Fulfillment API's Bearer Token authentication and clear endpoint documentation support rapid development. Most significant limitation is the lack of published rate limits and specific response schema documentation, requiring contact with WineDirect support for implementation details. Overall, integration feasibility is high with moderate development effort required.

---

## Sources

- [WineDirect APIs / Webservices Overview](https://docs.winedirect.com/docs/apis-webservices-overview)
- [WineDirect Integration Options](https://docs.winedirect.com/developer-docs/docs/winedirect-integration-options)
- [WineDirect Fulfillment API Guide](https://docs.winedirectfulfillment.com/api-guide/introduction)
- [Inventory Pools Documentation](https://docs.winedirect.com/docs/inventory-pools)
- [Inventory Reports](https://docs.winedirect.com/docs/inventory-reports)
- [WineDirect Documentation Portal](https://documentation.winedirect.com/)
- [ANWD Swagger API Specification](https://swagger.api.winedirect.com/?urls.primaryName=WineDirect%20API)
- [BigCommerce Developer Portal](https://developer.bigcommerce.com/)
