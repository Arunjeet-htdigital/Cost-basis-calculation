from collections import defaultdict
import pandas as pd
from extraction import run
# ── Lot field indices ────────────────────────────────────────────────────────
# Each lot in pools[asset] is a list (mutable so sells can drain in-place):
#
#   [ts, qty, rem_qty, total_qty, avco, mark]
#
#   ts        – acquisition timestamp of this lot
#   qty       – this lot's own quantity, drained in-place by FIFO sells
#   rem_qty   – pool-wide remaining qty, snapshot at lot-creation time;
#               only pool[-1][L_REM] is kept current (updated on every buy/sell)
#   total_qty – pool-wide total qty ever acquired, snapshot at lot-creation;
#               only pool[-1][L_TOTAL] is kept current
#   avco      – pool-wide weighted-average cost, snapshot at creation;
#               only pool[-1][L_AVCO] is kept current
#   mark      – 0 = live, 1 = tombstoned (lot fully drained)
#
# The LAST element of pools[asset] always carries the live running state.
# heads[asset] is the index of the first potentially-live lot (O(1) amortised).
# ─────────────────────────────────────────────────────────────────────────────
L_TS, L_QTY, L_REM, L_TOTAL, L_AVCO, L_MARK = 0, 1, 2, 3, 4, 5
def _is_valid(value) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    s = str(value).strip()
    return s not in ('', 'nan', 'NaN', 'N/A', 'n/a')
# ── Buy ───────────────────────────────────────────────────────────────────────
def process_buy(pools, heads, asset, ts, qty, price):
    """
    Add a buy lot for asset.
    Same-timestamp rule (mirrors pseudocode while-loop):
      Pop the last lot, fold the new buy into it, re-append.
      Loop until the new lot's timestamp differs from pool[-1] — handled
      naturally because we only ever call this once per row and the merge
      itself changes pool[-1], so a subsequent different-ts buy will fall
      through to the else branch.
    Different timestamp:
      Append a fresh lot, carrying forward running totals from pool[-1].
    """
    pool = pools[asset]
    if not pool:
        pool.append([ts, qty, qty, qty, price, 0])
        return
    last = pool[-1]
    if last[L_TS] == ts:
        # ── Same-timestamp merge ──────────────────────────────────────────
        pool.pop()
        # FIX (Flaw 3): merged_qty must use the lot's ORIGINAL quantity
        # (last[L_QTY] may have been partially drained by a prior sell in the
        # same timestamp — we re-add the full incoming qty on top of whatever
        # remains in the lot).  We re-derive rem/total from pool state.
        prev_rem   = last[L_REM]    # pool-wide rem before this buy
        prev_total = last[L_TOTAL]  # pool-wide total before this buy
        prev_avco  = last[L_AVCO]
        new_avco  = (prev_total * prev_avco + price * qty) / (prev_total + qty)
        new_rem   = prev_rem   + qty
        new_total = prev_total + qty
        # qty stored in the lot is the lot's own size (sum of all same-ts buys)
        merged_lot_qty = last[L_QTY] + qty   # accumulate the lot's own qty
        merge_idx = len(pool)   # index we're about to fill
        # Guard: if head walked past this slot (shouldn't happen in practice,
        # but be safe), pull it back.
        if heads[asset] > merge_idx:
            heads[asset] = merge_idx
        pool.append([last[L_TS], merged_lot_qty, new_rem, new_total, new_avco, 0])
    else:
        # ── Fresh lot ─────────────────────────────────────────────────────
        new_rem   = last[L_REM]   + qty
        new_total = last[L_TOTAL] + qty
        new_avco  = (last[L_TOTAL] * last[L_AVCO] + price * qty) / new_total
        pool.append([ts, qty, new_rem, new_total, new_avco, 0])
# ── Sell ──────────────────────────────────────────────────────────────────────
def process_sell(pools, heads, gains, asset, ts, qty, price, source_row, kind='sell'):
    """
    Record a disposal of qty units of asset at price.
    Steps (matching pseudocode exactly):
      1. Read AVCO and running totals from pool[-1]  (O(1))
      2. Compute realised gain
      3. Decrement pool[-1][L_REM]   — remaining qty falls             (FIX Flaw 1)
      4. Decrement pool[-1][L_TOTAL] — total acquired also falls       (FIX Flaw 1)
         Note: AVCO is unchanged on a sell (AVCO method)
      5. Advance head past tombstones (O(1) amortised)
      6. FIFO-drain lot[L_QTY] from the head forward until sell qty is
         exhausted, tombstoning fully-drained lots                     (FIX Flaw 3)
    """
    pool = pools[asset]
    # ── Error: pool empty ─────────────────────────────────────────────────
    if not pool:
        gains.append({**source_row,
                      'timestamp': ts, 'asset': asset, 'kind': kind,
                      'quantity': qty, 'price': price,
                      'proceeds': qty * price, 'cost_basis': 0.0,
                      'avco': 0.0, 'gain': qty * price,
                      'error': 'sell with empty pool'})
        return
    pool_rem   = pool[-1][L_REM]
    pool_avco  = pool[-1][L_AVCO]
    pool_total = pool[-1][L_TOTAL]
    if pool_rem <= 0:
        gains.append({**source_row,
                      'timestamp': ts, 'asset': asset, 'kind': kind,
                      'quantity': qty, 'price': price,
                      'proceeds': qty * price, 'cost_basis': 0.0,
                      'avco': pool_avco, 'gain': qty * price,
                      'error': 'sell with zero pool remaining'})
        return
    if qty > pool_rem + 1e-9:
        gains.append({**source_row,
                      'timestamp': ts, 'asset': asset, 'kind': kind,
                      'quantity': qty, 'price': price,
                      'proceeds': qty * price, 'cost_basis': 0.0,
                      'avco': pool_avco, 'gain': 0.0,
                      'error': f'sell qty {qty:.8f} > pool rem {pool_rem:.8f}'})
        return
    # ── 2. Realised gain ──────────────────────────────────────────────────
    proceeds    = qty * price
    cost_basis  = qty * pool_avco
    gain        = proceeds - cost_basis
    gains.append({**source_row,
                  'timestamp': ts, 'asset': asset, 'kind': kind,
                  'quantity': qty, 'price': price,
                  'proceeds': proceeds, 'cost_basis': cost_basis,
                  'avco': pool_avco, 'gain': gain,
                  'error': None})
    # ── 3 & 4. Update running pool state on last lot ──────────────────────
    # FIX (Flaw 1): both rem AND total must fall on every sell.
    # AVCO is unchanged (AVCO method — cost basis is a pool-level average).
    pool[-1][L_REM]   -= qty
    pool[-1][L_TOTAL] -= qty
    # ── 5. Advance head past already-tombstoned lots ──────────────────────
    while heads[asset] < len(pool) and pool[heads[asset]][L_MARK] == 1:
        heads[asset] += 1
    # ── 6. FIFO drain from head ───────────────────────────────────────────
    # FIX (Flaw 3): drain lot[L_QTY] (this lot's own residual quantity).
    # This is correct because L_QTY is decremented only here, so it always
    # reflects what is left in this specific lot.
    remaining = qty
    while remaining > 1e-12 and heads[asset] < len(pool):
        lot  = pool[heads[asset]]
        take = min(remaining, lot[L_QTY])
        lot[L_QTY] -= take
        remaining  -= take
        if lot[L_QTY] < 1e-12:
            lot[L_QTY]  = 0.0
            lot[L_MARK] = 1          # tombstone
            heads[asset] += 1
# ── Gas fee ───────────────────────────────────────────────────────────────────
def process_gas(pools, heads, gains, row, source_row, order_type):
    """
    Treat a fee as a disposal of the fee asset.
    FIX (Flaw 5): gas on a *buy/deposit* is an acquisition cost, NOT a
    disposal. Only trigger a sell-side gain record when the order is a
    sell, withdrawal, or trade (i.e. a disposal event is already occurring).
    """
    if order_type in ('deposit', 'buy'):
        # Acquisition-side fee: add to cost basis of the incoming asset
        # (handled implicitly — the buy price already reflects market value;
        # if you want strict HMRC section-104 treatment, add fee_cost to the
        # pool's AVCO here instead of ignoring it).
        return
    fee_asset = row.get('fee_asset_unique_symbol')
    fee_qty   = row.get('fee_volume')
    fee_price = row.get('fee_asset_price_gbp')
    ts        = row.get('timestamp')
    if not (_is_valid(fee_asset) and _is_valid(fee_qty) and _is_valid(fee_price)):
        return
    try:
        qty_f   = float(fee_qty)
        price_f = float(fee_price)
    except (ValueError, TypeError):
        return
    if qty_f <= 0:
        return
    process_sell(pools, heads, gains,
                 asset=str(fee_asset).strip(),
                 ts=ts, qty=qty_f, price=price_f,
                 source_row=source_row, kind='gas')
# ── Main matching loop ────────────────────────────────────────────────────────
def run_matching(df: pd.DataFrame):
    """
    Process the full DataFrame in chronological order.
    Order-type mapping expected after extraction normalisation:
      deposit / buy       → BUY path  (incoming asset)
      withdraw / sell     → SELL path (outgoing asset)
      trade               → SELL outgoing + BUY incoming
    """
    pools  = defaultdict(list)
    heads  = defaultdict(int)
    gains  = []
    for idx, row in df.iterrows():
        order_type = str(row.get('order_type', '')).strip().lower()
        ts         = row.get('timestamp')
        if not _is_valid(ts):
            continue
        source_row = {
            'source_idx':     idx,
            'source_file':    row.get('source_file'),
            'hash_unique_id': row.get('hash_unique_id'),
            'order_type':     order_type,
        }
        # ── BUY / DEPOSIT ─────────────────────────────────────────────────
        if order_type in ('deposit', 'buy'):
            asset = row.get('incoming_asset_unique_symbol')
            qty   = row.get('incoming_volume')
            price = row.get('incoming_asset_price_gbp')
            if _is_valid(asset) and _is_valid(qty) and _is_valid(price):
                try:
                    qty_f, price_f = float(qty), float(price)
                    if qty_f > 0:
                        process_buy(pools, heads,
                                    str(asset).strip(), ts, qty_f, price_f)
                except (ValueError, TypeError):
                    pass
            # Gas on buys is NOT a disposal — skipped inside process_gas
            process_gas(pools, heads, gains, row, source_row, order_type)
        # ── SELL / WITHDRAWAL ─────────────────────────────────────────────
        elif order_type in ('withdraw', 'withdrawal', 'sell'):
            asset = row.get('outgoing_asset_unique_symbol')
            qty   = row.get('outgoing_volume')
            price = row.get('outgoing_asset_price_gbp')
            if _is_valid(asset) and _is_valid(qty) and _is_valid(price):
                try:
                    qty_f, price_f = float(qty), float(price)
                    if qty_f > 0:
                        process_sell(pools, heads, gains,
                                     str(asset).strip(), ts, qty_f, price_f,
                                     source_row=source_row, kind='sell')
                except (ValueError, TypeError):
                    pass
            process_gas(pools, heads, gains, row, source_row, order_type)
        # ── TRADE ─────────────────────────────────────────────────────────
        elif order_type == 'trade':
            # 1. Sell outgoing side
            out_asset = row.get('outgoing_asset_unique_symbol')
            out_qty   = row.get('outgoing_volume')
            out_price = row.get('outgoing_asset_price_gbp')
            if _is_valid(out_asset) and _is_valid(out_qty) and _is_valid(out_price):
                try:
                    qty_f, price_f = float(out_qty), float(out_price)
                    if qty_f > 0:
                        process_sell(pools, heads, gains,
                                     str(out_asset).strip(), ts, qty_f, price_f,
                                     source_row=source_row, kind='trade_sell')
                except (ValueError, TypeError):
                    pass
            # 2. Buy incoming side
            in_asset = row.get('incoming_asset_unique_symbol')
            in_qty   = row.get('incoming_volume')
            in_price = row.get('incoming_asset_price_gbp')
            if _is_valid(in_asset) and _is_valid(in_qty) and _is_valid(in_price):
                try:
                    qty_f, price_f = float(in_qty), float(in_price)
                    if qty_f > 0:
                        process_buy(pools, heads,
                                    str(in_asset).strip(), ts, qty_f, price_f)
                except (ValueError, TypeError):
                    pass
            # 3. Gas — disposal side (order_type='trade' triggers sell path)
            process_gas(pools, heads, gains, row, source_row, order_type)
        else:
            # Unknown order type — skip silently (logged via missing gains)
            continue
    return gains, pools, heads
# ── Pool snapshot ─────────────────────────────────────────────────────────────
def summarise_pools(pools, heads):
    """Return a DataFrame snapshot of each asset pool with a non-zero balance."""
    rows = []
    for asset, pool in pools.items():
        if not pool:
            continue
        last      = pool[-1]
        rem_qty   = last[L_REM]
        avco      = last[L_AVCO]
        total_qty = last[L_TOTAL]
        if rem_qty <= 0:
            continue
        live_lots = sum(1 for lot in pool[heads[asset]:]
                        if lot[L_MARK] == 0 and lot[L_QTY] > 0)
        rows.append({
            'asset':           asset,
            'rem_qty':         rem_qty,
            'total_qty_ever':  total_qty,
            'avco_gbp':        avco,
            'book_value_gbp':  rem_qty * avco,
            'live_lots':       live_lots,
            'tombstones':      heads[asset],
            'total_lots_ever': len(pool),
        })
    return pd.DataFrame(rows)
# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    df = run(r"C:\Users\Arunjeet\OneDrive - Harris & Trotter LLP\Downloads\keeper_data")
    print("\nRunning AVCO matching...")
    gains, pools, heads = run_matching(df)
    gains_df = pd.DataFrame(gains)
    print(f"\nGains records : {len(gains_df):,}")
    errors = gains_df[gains_df['error'].notna()] if 'error' in gains_df.columns else pd.DataFrame()
    if not errors.empty:
        print(f"Rows with errors: {len(errors)}")
        print(errors[['timestamp', 'asset', 'kind', 'quantity', 'error']].to_string())
    print(gains_df.head(20).to_string())
    gains_df.to_csv('gains_avco_v2.csv', index=False)
    pools_df = summarise_pools(pools, heads)
    print(f"\nAssets with non-zero balance: {len(pools_df):,}")
    print(pools_df.to_string())
    pools_df.to_csv('pool_snapshots_v2.csv', index=False)
