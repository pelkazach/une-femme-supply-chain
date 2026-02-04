# Spec: Distributor Data Processing

## Job to Be Done
As a supply chain operator, I need to process CSV/Excel files from distributors (RNDC, Southern Glazers, Winebow) so that I can track depletion allowances and inventory across all distribution channels without relying on unavailable APIs.

## Requirements
- Create file upload endpoint accepting CSV and Excel formats
- Parse standard distributor report formats (RNDC, Southern Glazers, Winebow)
- Validate data fields (SKU matching, quantity validation, date parsing)
- Transform distributor data into unified internal schema
- Insert processed data into inventory_events table
- Support custom templates for additional distributors
- Log processing results and flag validation errors

## Acceptance Criteria
- [ ] CSV upload endpoint accepts multipart/form-data
- [ ] Excel (.xlsx) files parsed correctly
- [ ] RNDC report format parsed with all required fields
- [ ] Southern Glazers report format parsed with all required fields
- [ ] Winebow report format parsed with all required fields
- [ ] Invalid rows flagged with specific error messages
- [ ] Valid rows inserted into inventory_events
- [ ] Processing summary returned (success count, error count)

## Test Cases
| Input | Expected Output |
|-------|-----------------|
| Valid RNDC CSV (100 rows) | 100 inventory_events created |
| CSV with unknown SKU | Row flagged, error logged, others processed |
| Excel with multiple sheets | Primary sheet processed, warning logged |
| Malformed date format | Row rejected with "invalid date" error |
| Empty file | Error: "No data rows found" |
| Custom template upload | Template saved, future files use mapping |

## Technical Notes
- Distributor APIs are limited; file-based is industry standard
- Tradeparency model: Pre-trained on major distributor formats
- Required fields: Date, SKU, Quantity, Distributor, Event Type
- Support both depletion reports and billback documentation
- Consider pandas for Excel parsing, built-in csv for CSV

## File Format Specifications

### RNDC Report
```
Date,Invoice,Account,SKU,Description,Qty Sold,Unit Price,Extended
2026-01-15,INV001,ABC Liquor,UFBub250,Une Femme Brut 250ml,24,12.99,311.76
```

### Southern Glazers Report
```
Ship Date,Customer,Item Code,Item Description,Cases,Bottles,Amount
01/15/2026,XYZ Wine Bar,UFRos250,Une Femme Rose 250ml,10,120,1558.80
```

### Winebow Report
```
transaction_date,customer_name,product_code,product_name,quantity,total
2026-01-15,Fine Wines Inc,UFRed250,Une Femme Red 250ml,48,623.52
```

## Distributor Segment Mapping
| Segment | Distributors |
|---------|-------------|
| Non-RNDC States | Various regional |
| Georgia (RNDC) | RNDC Georgia division |
| Reyes 7 States | Reyes Beverage Group |
| Other RNDC States | RNDC other divisions |

## Source Reference
- [[andavi-tradeparency]] - CSV/Excel integration model
- [[edi-wine-distribution]] - Industry data format standards
