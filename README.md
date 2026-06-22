# Cost-basis-calculation

# Readme for accountants
# Cost Basis Calculation-Accountant's Guide

# OUTPUT--Keeps track of Cost basis as a subledger with additional features like running balance per address per token. Can be easily validated onchain at periodic intervals...
# Validates with edge cases. Keeps track of possible errors without silent failures...
<img width="1405" height="707" alt="image" src="https://github.com/user-attachments/assets/80661d30-f544-462e-ae43-2ea94a738ca9" />


## What This Tool Does

This tool calculates the cost basis and gains/losses for cryptocurrency transactions using the **Average Cost (AVCO)** method. It processes exchange transaction exports and produces auditable monthly summaries showing inventory values, gains, and losses per asset.

**Core Calculation:** For each asset sold, cost is determined using the weighted average cost of all units held, adjusted for any fees paid.

**Why AVCO?** The Average Cost method is accepted by HMRC (UK tax authority) and most accountancy bodies for crypto cost basis. It's simpler than FIFO/LIFO and reflects economic reality for volatile assets.

## When to Use This Tool

✓ You need to calculate taxable gains on cryptocurrency sales  
✓ You're reconciling exchange transactions to your GL  
✓ You're preparing a crypto asset schedule for financial statements  
✓ You need monthly or periodic cost basis valuations  
✓ You need to support tax filings with transaction detail  

✗ You're doing a real-time portfolio valuation (use price feeds instead)  
✗ You need intraday reconciliation (this processes daily/transaction level only)  

## Input Requirements

### Source Data: Exchange Exports

You'll need XLSX (Excel) export files from cryptocurrency exchanges. Common sources: Coinbase, Kraken, Gemini, Huobi, etc.

**Required Information in Exports:**

Each transaction export should include:

| Item | What It Is | Example |
|------|-----------|---------|
| **Transaction Hash/ID** | Unique identifier for each trade | "0x1a2b3c4d..." |
| **Date & Time** | When the transaction settled (UTC) | "2024-01-15 14:30:00" |
| **Exchange/Source** | Where the transaction occurred | "Coinbase Pro" |
| **Transaction Type** | What happened | "buy", "sell", "trade", "deposit", "withdraw" |
| **Asset Received** | What you got | "ETH", "USDC", "BTC" |
| **Quantity Received** | How much | 2.5 ETH |
| **Unit Price (GBP)** | Price per unit in GBP | £1,800 / ETH |
| **Asset Sent** | What you sold/swapped | "USDC", "GBP", "BTC" |
| **Quantity Sent** | How much | 4,500 USDC |
| **Unit Price (GBP)** | Price per unit in GBP | £0.85 / USDC |
| **Fees** | Transaction costs (optional) | £25 GBP |
| **Wallet** | Your internal wallet identifier | "Trading-Wallet-1" |
| **Labels/Notes** | Optional tags | "airdrop", "staking" |

### Before You Start

1. **Gather all exchange exports** for the period covered (usually a calendar year)
2. **Convert all prices to GBP** if your exchanges report in other currencies
3. **Ensure consistent wallet naming** across all exports (use a standard list)
4. **Verify timestamps are in UTC** (not local time)
5. **Remove sensitive data** if files are shared (addresses, PII can stay for reconciliation)
6. **Check for completeness:**
   - Every buy/deposit is matched with corresponding inventory movement
   - No duplicate transactions in the export
   - All conversions (BTC → GBP, etc.) are captured

### File Format

Exports should be **XLSX files** (Excel format). One file per export or multiple files in a single folder.

**Folder Structure Example:**
```
transaction_data/
├── Coinbase_Jan-Mar_2024.xlsx
├── Kraken_Apr-Jun_2024.xlsx
└── Gemini_Jul-Dec_2024.xlsx
```

The tool will automatically combine all XLSX files in a folder.

## Step-by-Step Usage

### Step 1: Prepare Your Export Files

Export transactions from each exchange covering your required period. Ensure all files are in XLSX format and placed in a single folder.

### Step 2: Run the Tool

Open a terminal/command line and run:

```bash
python processing.py "C:\path\to\your\transaction_data"
```

**Output:** `testing_dump.csv` (cleaned transaction list)

This file shows all transactions in standardized format with normalized column names. Review for:
- Total row count matches your exports
- All assets are recognized (no typos)
- Timestamps are in order

### Step 3: Generate Monthly Summaries

Run the analysis:

```bash
python analysis.py
```

**Output:** `analysis.csv` (monthly summaries)

This is your main report showing:
- Monthly transactions by wallet and asset
- Total quantity bought/sold
- Cost basis applied
- Gains/losses realized
- Ending inventory

### Step 4: Reconcile to General Ledger

Open `analysis.csv` in Excel and cross-check:

1. **Total gains should match** your realized gain/loss GL account for the period
2. **Ending inventory quantities** should match your balance sheet crypto holdings
3. **By-asset totals** should reconcile to corresponding subledger accounts

Example reconciliation:

| Asset | GL Balance | Analysis CSV Total | Difference |
|-------|------------|-------------------|-----------|
| ETH | 5.25 units | 5.25 units | ✓ Match |
| BTC | 0.10 units | 0.10 units | ✓ Match |

### Step 5: Export for Tax Filing / Audit

Use `analysis.csv` as the basis for:
- Capital gains/losses schedule (attach to tax return)
- Asset footnote in financial statements
- Audit working paper for cost basis support

## Understanding the Output

### analysis.csv — Key Columns Explained

| Column | Meaning | What to Look For |
|--------|---------|-----------------|
| **month** | Report period (YYYY-MM) | January = 2024-01 |
| **wallet** | Your wallet identifier | Consistency across filing |
| **asset** | Cryptocurrency symbol | ETH, BTC, USDC, etc. |
| **kind** | Transaction type | "buy", "sell", "trade" |
| **total** | # of transactions | High count = complex trading |
| **total_quantity** | Sum of units | For reconciliation |
| **total_proceeds** | Sale value (GBP) | "Proceeds" for tax forms |
| **total_cost_basis** | Acquisition cost (GBP) | "Cost basis" for tax forms |
| **max_avco** | Weighted avg cost at end of month | Unit price for inventory valuation |
| **total_gain** | Realized gain/(loss) | = proceeds - cost basis |
| **total_left** | Ending inventory (units) | Reconcile to balance sheet |

### Calculating Taxable Gain

For each sale (kind = "sell"):

```
Taxable Gain = (Total Proceeds) − (Total Cost Basis)
             = total_proceeds − total_cost_basis
```

If negative, it's a capital loss (which can offset other gains).

**Example:**
- Sold 1 ETH in March
- Total Proceeds: £2,500
- Total Cost Basis: £1,800 (calculated by tool)
- **Taxable Gain: £700**

### AVCO Method Explanation

The tool uses Average Cost (AVCO) to determine which purchased units are sold:

**Step 1:** Calculate weighted average cost
```
AVCO = Total Cost of All Units Held / Total Units Held
```

**Step 2:** Apply that cost to units sold
```
Cost of Sale = Units Sold × AVCO
```

**Example:**
- You hold 2 ETH: 1 bought at £1,000, 1 bought at £1,500
- AVCO = (1,000 + 1,500) / 2 = £1,250 per ETH
- You sell 1 ETH: Cost basis = 1 × £1,250 = £1,250
- If sold for £2,000: Gain = £2,000 − £1,250 = £750

**Why AVCO?**
- Reflects the economic mix of inventory you're selling
- Accepted by HMRC and UK accountancy bodies (ICAEW)
- More stable than FIFO/LIFO in volatile crypto markets
- Simpler to defend in audit vs. coin-tracking methods

## Reconciliation Checklist

Before finalizing for tax or audit:

- [ ] Total transactions in `testing_dump.csv` match exchange exports
- [ ] All wallets are named consistently (no typos)
- [ ] No duplicates detected (check for identical hash + timestamp)
- [ ] Ending inventory quantities match your current holdings
- [ ] Fees are included in cost basis calculations
- [ ] Currency (all GBP) is consistent
- [ ] Date range covers the full reporting period (Jan 1 – Dec 31)
- [ ] No staking/rewards if they shouldn't be included
- [ ] Deposits and withdrawals are correctly classified (not mixed in sales)
- [ ] Gains/losses flow to correct GL accounts

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| **Inventory quantity doesn't match balance sheet** | Missing deposits or transfers in exports | Check all wallet sources are included in extract |
| **Gains are too high/low** | Price data is incomplete or wrong currency | Verify all *_price_gbp fields are populated; convert all prices to GBP |
| **No data appears** | File path wrong or export format not recognized | Confirm XLSX files in folder; check for "hash" column header |
| **AVCO seems incorrect** | Fees not captured or transaction order wrong | Ensure fees are in source data; verify timestamps are UTC and correct |
| **Duplicate transactions appear** | Multiple exports of same exchange period | Remove duplicate files or filter in tool config |

## Adjustments & Exceptions

### Handling Airdrops & Staking Rewards

If your exchange exports include rewards/airdrops and you don't want to include them in cost basis:

1. **Option A (Recommended):** Filter before running tool
   - Manually remove rows labeled "airdrop", "staking reward" from XLSX
   - Run tool on cleaned files

2. **Option B:** Post-process in Excel
   - Open `analysis.csv`
   - Filter out "labels" containing "airdrop" or "reward"
   - Recalculate totals

3. **For tax:** Record airdrops separately
   - Date received and fair value = income (not cost basis)
   - Attach separate schedule to tax return

### Wash Sales & Tracking Lots

This tool does **not** track specific lots (individual purchases). AVCO treats all units of an asset as a pool.

**If you need to apply UK tax wash sale rules (30-day matching rule for losses):**
- Export `testing_dump.csv`
- Use a separate "lot tracking" spreadsheet to manually apply 30-day rule
- Adjust cost basis entries in analysis as needed

### Adjusting for Errors in Source Data

If you discover errors in the original exchange export after running analysis:

1. Correct the XLSX file
2. Delete `testing_dump.csv` and `analysis.csv`
3. Re-run: `python processing.py <folder>`
4. Re-run: `python analysis.py`

All outputs regenerate automatically.

## Reconciliation to Financial Statements

### For the Balance Sheet

**Crypto Asset Schedule (as of period-end date):**

| Asset | Units | Unit Cost (AVCO) | Total Book Value |
|-------|-------|------------------|-----------------|
| BTC | 0.25 | £19,500 | £4,875 |
| ETH | 5.00 | £1,250 | £6,250 |
| USDC | 10,000 | £0.87 | £8,700 |
| **Total Crypto** | | | **£19,825** |

Source: `analysis.csv` → `max_avco` column (unit cost) × `total_left` (ending inventory)

### For the Income Statement

**Realized Gains/(Losses) Schedule (for period):**

| Asset | # Sales | Proceeds | Cost Basis | Gain/(Loss) |
|-------|---------|----------|-----------|------------|
| ETH | 3 | £12,500 | £9,000 | £3,500 |
| BTC | 1 | £18,000 | £16,500 | £1,500 |
| USDC | 2 | £8,500 | £8,450 | £50 |
| **Total Realized** | | **£39,000** | **£33,950** | **£5,050** |

Source: `analysis.csv` → Filter kind="sell" → Sum `total_gain`

### For Tax Reporting

**Capital Gains Summary (for Self Assessment / CT600):**

| Period | Proceeds | Cost Basis | Gain/(Loss) |
|--------|----------|-----------|------------|
| Jan-Mar 2024 | £15,000 | £12,000 | £3,000 |
| Apr-Jun 2024 | £18,000 | £16,500 | £1,500 |
| Jul-Dec 2024 | £6,000 | £5,450 | £550 |
| **Total 2024** | **£39,000** | **£33,950** | **£5,050** |

Net gain = £5,050 (taxable at your marginal rate after annual exemption)

## Data Privacy & Security

- Keep XLSX exports secure (contain transaction hashes + amounts)
- Don't share `testing_dump.csv` or `analysis.csv` with external parties without sanitizing
- Archive outputs in secure folder (similar to GL backups)
- Retention: Keep for 6 years (UK tax requirement)

## Limitations & Disclaimers

1. **AVCO Method Only:** This tool calculates cost basis using Average Cost. If you need FIFO, LIFO, or specific lot identification, you'll need a different tool or manual tracking.

2. **No Price Feed:** The tool uses prices from your exchange export. It does **not** fetch current market prices; it's historical-only.

3. **Manual Adjustments Required:** This tool processes exchange data. Non-exchange transactions (peer-to-peer, mining, staking) must be added separately.

4. **Tax Jurisdiction:** All prices are in GBP and calculations assume UK tax treatment. Consult your tax advisor for other jurisdictions.

5. **Audit Trail:** This tool should be run on a consistent schedule by the same person for audit consistency. Document the run date and parameters if audited.

## Audit Support

When your external auditors ask about cost basis:

**Provide:**
1. `testing_dump.csv` (transaction detail)
2. `analysis.csv` (monthly summaries)
3. Description of methodology (AVCO, GBP, period covered)
4. Screenshots showing reconciliation to GL

**Be ready to explain:**
- Why AVCO was chosen
- How prices were sourced and converted
- Any manual adjustments made post-run
- How ending inventory was verified

## Contact & Support

Questions on accounting treatment? Consult:
- **HMRC Crypto Guidance:** https://www.gov.uk/guidance/tax-on-cryptoassets
- **ICAEW Guidance:** Search "cryptocurrency accounting"
- **Your tax advisor:** For jurisdiction-specific treatment

Technical issues? See the Developer README or file a GitHub issue with sample data.

---

**Last Updated:** January 2025  
**For:** UK Accountants & Finance Teams  
**Method:** AVCO (Weighted Average Cost)  
**Currency:** GBP


# Cost Basis Calculation — Input & Output Schema Reference

## Input Schema (XLSX Format)

### Expected XLSX Structure

The tool expects XLSX files containing cryptocurrency exchange transaction exports with the following structure:

**Header Row Trigger:** Column containing "hash" (case-insensitive)

Once the header is located, the tool normalizes column names and extracts relevant fields.

### Column Mapping & Requirements

| Original XLSX Column | Normalized Name | Type | Required | Notes |
|---------------------|-----------------|------|----------|-------|
| Wallet | wallet | String | ✓ | Unique identifier for your wallet/account |
| Transaction Hash, Tx ID | hash_unique_id | String | ✓ | Unique transaction identifier |
| Date, Date (UTC), Timestamp | date_utc | DateTime | ✓ | Transaction time in UTC |
| Exchange, Source, Platform | source_name | String | ✓ | Exchange name (e.g., "Coinbase", "Kraken") |
| Type, Order Type, Tx Type | order_type | String | ✓ | One of: deposit, buy, trade, sell, withdraw |
| Received Asset, In Asset, Incoming | incoming_asset_unique_symbol | String | ~ | Symbol of asset received (e.g., ETH) |
| Received Qty, Received Vol, In Vol | incoming_volume | Float | ~ | Quantity of asset received |
| Received Price (GBP), In Price GBP | incoming_asset_price_gbp | Float | ~ | Unit price in GBP of received asset |
| Sent Asset, Out Asset, Outgoing | outgoing_asset_unique_symbol | String | ~ | Symbol of asset sent/sold |
| Sent Qty, Sent Vol, Out Vol | outgoing_volume | Float | ~ | Quantity of asset sent |
| Sent Price (GBP), Out Price GBP | outgoing_asset_price_gbp | Float | ~ | Unit price in GBP of sent asset |
| Fee Asset, Fee Token | fee_asset_unique_symbol | String | ✗ | Asset used for fees (if applicable) |
| Fee Qty, Fee Volume | fee_volume | Float | ✗ | Quantity of fee paid |
| Fee Price (GBP) | fee_asset_price_gbp | Float | ✗ | Unit price of fee asset in GBP |
| Fee Cost Basis (GBP) | fee_book_value_gbp | Float | ✗ | Cost basis of fee in GBP |
| Fee Value (GBP) | fee_value_gbp | Float | ✗ | Total fee value in GBP |
| Internal Transfer | internal_transfer | String | ✗ | YES / NO (whether transfer between own wallets) |
| Labels, Tags, Notes | labels | String | ✗ | Transaction tags (e.g., "airdrop", "staking reward") |
| Counterparty, Address | other_parties | String | ✗ | Counterparty address or name |

**Legend:**
- ✓ Required (data quality check will fail if missing/empty)
- ~ Conditionally required (needed based on transaction type)
- ✗ Optional (improves reconciliation but not required)

### Column Normalization Rules

The tool automatically normalizes column names using these rules:

```
1. Convert to lowercase
2. Replace spaces, slashes, parentheses with underscores
3. Collapse multiple underscores to single underscore
4. Strip leading/trailing underscores
```

**Examples:**
- "Incoming Asset (Unique Symbol)" → `incoming_asset_unique_symbol`
- "Fee / Cost Basis (GBP)" → `fee_cost_basis_gbp`
- "Tx  ID" → `tx_id`

### Data Type Specifications

| Type | Format | Examples |
|------|--------|----------|
| String | Text | "ETH", "Coinbase Pro", "0x1a2b3c" |
| DateTime | ISO 8601 UTC | "2024-01-15T14:30:00Z" or "2024-01-15 14:30:00" |
| Float | Decimal number | 1.5, 0.00001, 1234.56 |
| Integer | Whole number | 1, 100, 500 |

### Transaction Type Precedence

When sorting transactions, the tool applies this priority (lowest processed first):

```python
{
    'deposit':    0,    # ← Process first (add to inventory)
    'buy':        0,
    'trade':      1,    # ← Process second (swap assets)
    'sell':       2,    # ← Process last (reduce inventory)
    'withdraw':   2,
    'withdrawal': 2,
}
```

**Importance:** This ensures cost basis is calculated correctly. A buy must be recorded before a sell of the same asset.

### Conditional Requirements by Transaction Type

#### Deposit / Buy / Incoming

Must have:
- `order_type` = "deposit" or "buy"
- `incoming_asset_unique_symbol` (what you received)
- `incoming_volume` (how much)
- `incoming_asset_price_gbp` (price per unit in GBP)

Optional:
- `fee_asset_unique_symbol`, `fee_volume`, `fee_value_gbp` (transaction costs)

#### Sell / Withdraw / Outgoing

Must have:
- `order_type` = "sell" or "withdraw"
- `outgoing_asset_unique_symbol` (what you sent)
- `outgoing_volume` (quantity)
- `outgoing_asset_price_gbp` (GBP price per unit)

Optional:
- `fee_*` fields (if applicable)

#### Trade / Swap

Must have:
- `order_type` = "trade"
- `incoming_asset_unique_symbol`, `incoming_volume`, `incoming_asset_price_gbp`
- `outgoing_asset_unique_symbol`, `outgoing_volume`, `outgoing_asset_price_gbp`

Optional:
- `fee_*` fields

### Validation Rules

The tool will **accept** records where:
- All required fields are populated (not null/empty)
- Timestamps are parseable as datetime
- Numeric fields contain valid numbers (not text like "N/A")
- Asset symbols match across transactions (no typos)

The tool will **skip or flag** records where:
- Header row not found
- Timestamp cannot be parsed (marked NaT)
- Duplicate hash_unique_id + timestamp (first kept, duplicates dropped)
- Column name doesn't match expected schema

---

## Output Schema

### Output 1: testing_dump.csv

**Purpose:** Cleaned, sorted transaction records (detail level)

**Rows:** One row per transaction

**Column Definitions:**

| Column | Type | Description |
|--------|------|-------------|
| timestamp | DateTime | Transaction time (ISO 8601 UTC) |
| hash_unique_id | String | Unique transaction ID from source |
| source_file | String | XLSX filename from which this record came |
| wallet | String | Your wallet identifier |
| source_name | String | Exchange name |
| order_type | String | Transaction type (deposit, buy, trade, sell, withdraw) |
| incoming_asset_unique_symbol | String | Asset received (symbol) |
| incoming_volume | Float | Quantity received |
| incoming_asset_price_gbp | Float | Unit price of received asset (GBP) |
| outgoing_asset_unique_symbol | String | Asset sent (symbol) |
| outgoing_volume | Float | Quantity sent |
| outgoing_asset_price_gbp | Float | Unit price of sent asset (GBP) |
| fee_asset_unique_symbol | String | Asset used for fees (if applicable) |
| fee_volume | Float | Fee quantity |
| fee_asset_price_gbp | Float | Fee asset price (GBP) |
| fee_book_value_gbp | Float | Fee cost basis (GBP) |
| fee_value_gbp | Float | Total fee (GBP) |
| internal_transfer | String | "YES" or "NO" |
| labels | String | Tags/notes |
| address | String | Counterparty address |

**Row Order:**
- Sorted by: timestamp → transaction type precedence
- Earliest transactions first

**Usage:**
- Verify transaction counts match source exports
- Debug missing or incorrect data
- Spot-check prices and quantities
- Identify duplicates or errors

### Output 2: analysis.csv

**Purpose:** Monthly summaries by wallet, asset, and transaction type (reporting level)

**Rows:** One row per (month, wallet, asset, transaction_type) combination

**Column Definitions:**

| Column | Type | Description |
|--------|------|-------------|
| month | String | Report period (YYYY-MM format) |
| wallet | String | Wallet identifier |
| asset | String | Cryptocurrency symbol (e.g., ETH, BTC) |
| kind | String | Transaction type (buy, sell, trade, etc.) |
| id | Integer | Highest transaction ID in this month |
| total | Integer | Count of transactions in this group |
| total_quantity | Float | Sum of transaction quantities |
| total_proceeds | Float | Sum of sale proceeds (GBP) |
| total_cost_basis | Float | Total cost applied to transactions (GBP) |
| max_avco | Float | **Weighted average cost per unit (GBP)** |
| total_gain | Float | Realized gain or loss (proceeds − cost basis) |
| error_count | Integer | # of records with parsing errors |
| total_left | Float | Ending inventory quantity |

### Key Formulas in analysis.csv

**Realized Gain/Loss (Taxable):**
```
total_gain = total_proceeds − total_cost_basis
```

**Weighted Average Cost (AVCO) per Unit:**
```
max_avco = total_cost_basis / total_quantity
```
(Used to value ending inventory and cost future sales)

**Ending Inventory Value:**
```
ending_value = total_left × max_avco
```

### Data Integrity Checks

After running, verify:

1. **Row counts:** `SUM(total_quantity)` in testing_dump = `total_left` by asset
2. **No nulls in key columns:** month, wallet, asset, kind, total_gain
3. **Positive quantities:** total_quantity and total_left > 0
4. **Positive costs:** total_cost_basis ≥ 0
5. **AVCO reasonableness:** max_avco > 0 and aligns with GBP market prices

---

## Common Data Scenarios & How They Map

### Scenario 1: Simple Buy

**XLSX Input:**
| wallet | hash | timestamp | order_type | incoming_asset_unique_symbol | incoming_volume | incoming_asset_price_gbp |
|--------|------|-----------|-----------|------|---------|---------|
| Trading-1 | tx001 | 2024-01-10 | buy | ETH | 1.0 | 2000 |

**testing_dump.csv Output:**
- One row, all fields populated
- outgoing_* fields empty (you bought with GBP/existing cash)

**analysis.csv Output:**
- Month: 2024-01
- Wallet: Trading-1
- Asset: ETH
- Kind: buy
- total_quantity: 1.0
- total_cost_basis: 2000
- max_avco: 2000
- total_left: 1.0 (inventory +1)

### Scenario 2: Sell with AVCO

**Existing Inventory:**
- 2 ETH at AVCO £1,500 = £3,000 cost

**XLSX Input:**
| wallet | hash | timestamp | order_type | outgoing_asset_unique_symbol | outgoing_volume | outgoing_asset_price_gbp |
|--------|------|-----------|-----------|---------|---------|---------|
| Trading-1 | tx002 | 2024-02-15 | sell | ETH | 1.0 | 2500 |

**Calculation by Tool:**
- AVCO applied to sale: 1 × £1,500 = £1,500 cost
- Proceeds: 1 × £2,500 = £2,500
- Gain: £2,500 − £1,500 = £1,000

**analysis.csv Output:**
- total_proceeds: 2500
- total_cost_basis: 1500
- total_gain: 1000
- total_left: 1.0 (remaining 1 ETH)

### Scenario 3: Multi-Asset Trade (Swap)

**XLSX Input:**
| wallet | hash | timestamp | order_type | incoming_asset | incoming_volume | incoming_price_gbp | outgoing_asset | outgoing_volume | outgoing_price_gbp |
|--------|------|-----------|-----------|---------|---------|---------|---------|---------|---------|
| Trading-1 | tx003 | 2024-03-20 | trade | BTC | 0.05 | 30000 | ETH | 1.0 | 1500 |

**Tool Processing:**
- Records as two transactions:
  1. ETH outgoing (sold/swapped)
  2. BTC incoming (received)

**analysis.csv Output (Two Rows):**
- Row 1: asset=ETH, kind=trade, proceeds=1500, cost_basis=(AVCO × 1)
- Row 2: asset=BTC, kind=trade, total_cost_basis=1500 (matched to proceeds)

### Scenario 4: Multiple Deposits → Single Sale

**XLSX Input:**
| Date | Asset | Type | Volume | Price |
|------|-------|------|--------|-------|
| 2024-01-10 | ETH | deposit | 2.0 | 1000 |
| 2024-01-15 | ETH | buy | 1.0 | 1200 |
| 2024-02-20 | ETH | sell | 1.5 | 1800 |

**AVCO Calculation by Tool:**
- Inventory: 3 ETH at cost = (2×1000 + 1×1200) = £3,200
- AVCO = 3,200 / 3 = £1,066.67 per ETH
- Sale cost: 1.5 × 1,066.67 = £1,600
- Proceeds: 1.5 × 1,800 = £2,700
- Gain: £2,700 − £1,600 = £1,100

**analysis.csv Rows:**
- Jan: buy (deposits), total_left = 3 ETH
- Feb: sell, cost_basis = 1600, proceeds = 2700, gain = 1100, total_left = 1.5

---

## Troubleshooting Data Issues

### Issue: "No header row found"

**Cause:** Column containing "hash" not detected

**Fix:**
1. Ensure XLSX has a header row with "hash" or similar column name
2. Check for typos (should match "hash*" case-insensitive)
3. Verify header is in row 1 or row 2 (not buried deeper)

### Issue: Timestamp parsing errors (NaT values)

**Cause:** Date format not recognized

**Fix:**
1. Ensure `date_utc` column is formatted as Date in Excel
2. Verify dates are in ISO 8601 format (YYYY-MM-DD HH:MM:SS)
3. Check timezone is UTC (not local)

### Issue: Quantities don't match ending inventory

**Cause:** Missing transactions or duplicate removal

**Fix:**
1. Verify all XLSX files are in the input folder
2. Check for duplicate transactions (same hash, timestamp, exchange)
3. Inspect testing_dump.csv for row count

### Issue: AVCO shows as 0 or null

**Cause:** Missing price data

**Fix:**
1. Populate `incoming_asset_price_gbp` for all buys/deposits
2. Populate `outgoing_asset_price_gbp` for all sells
3. Ensure prices are numeric (not text like "£2,000")

---

## Data Quality Checklist

Before running analysis, verify:

- [ ] All XLSX files are in correct folder
- [ ] Header row exists in each file (contains "hash")
- [ ] All timestamps are in UTC and parseable
- [ ] All prices are in GBP (converted if needed)
- [ ] Asset symbols are consistent (no "ETH" vs "eth" mix)
- [ ] Wallet names match across files
- [ ] No obviously duplicate transactions (same hash + timestamp)
- [ ] Numeric fields don't contain text (e.g., "N/A", commas)
- [ ] No missing required fields (transaction type, asset, quantity, price)
- [ ] Date range covers intended period (Jan 1 – Dec 31 for tax year)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2025 | Initial release; AVCO method, GBP currency, XLSX input |

## Additional Resources

- **Developer README:** See `README_DEVELOPER.md` for technical setup and customization
- **Accountant README:** See `README_ACCOUNTANT.md` for usage, reconciliation, and tax reporting
- **GitHub:** [Arunjeet-htdigital/Cost-basis-calculation](https://github.com/Arunjeet-htdigital/Cost-basis-calculation)


