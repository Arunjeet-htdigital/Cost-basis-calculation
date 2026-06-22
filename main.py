from collections import defaultdict, deque
import pandas as pd
from extraction import run
from info import snapshot
import sys

# ── Lot layout ────────────────────────────────────────────────────────────────
#
#   lot = (date, quantity, total_quantity, avco)
#
#   date           – acquisition timestamp of this lot
#   quantity       – this lot's own size; drained by FIFO sells from pool[0]
#   total_quantity – pool-wide running balance; only pool[-1] is current
#                    incremented on buys, decremented on sells
#   avco           – pool-wide weighted-average cost; only pool[-1] is current
#                    updated on buys, unchanged on sells
#
# d30p[asset]      – deque of live lots, index 0=oldest (FIFO front), -1=newest
# graveyard[asset] – fully-drained lots moved here from front; audit trail only
#
# Key invariants:
#   Buys  → only touch pool[-1] (pop + append), never pool[0]
#   Sells → pop/append pool[-1] for total update, then FIFO drain from pool[0]
#            FIFO drain stops at len(pool)==1 — the last lot is the pool state
#            carrier and must never be consumed by the drain loop
# ─────────────────────────────────────────────────────────────────────────────




L_DATE, L_QTY, L_TOTAL, L_AVCO = 0, 1, 2, 3


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

def process_buy(d30p, gains, is_internal, wallet, asset, date, quantity_n, price_n, source_row, kind='buy'):
    """
    Same-timestamp merge (while loop):
        Accumulate qty and cost for all units acquired at this timestamp.
        Recover pre-timestamp pool state from the last popped lot:
            old_total = lot_total - lot_qty   (lot_total includes this lot)
            old_cost  = old_total * lot_avco

        After loop:
            total_quantity = old_total + new_qty
            new_avco       = (old_cost + new_cost) / total_quantity

    Different timestamp: fresh append carrying total and avco from pool[-1].
    """
    pool = d30p[wallet][asset]

    if not pool:
        pool.append((date, quantity_n, quantity_n, price_n))
        return

    if pool[-1][L_DATE] != date:
        # ── Fresh lot ─────────────────────────────────────────────────────
        last      = pool[-1]
        new_total = last[L_TOTAL] + quantity_n
        new_avco  = (last[L_TOTAL] * last[L_AVCO] + price_n * quantity_n) / new_total
        pool.append((date, quantity_n, new_total, new_avco))


        gains.append({**source_row,
                'timestamp': date, 'wallet': wallet,'asset': asset, 'kind': kind,
                'quantity': quantity_n, 'price': price_n,
                'proceeds': None, 'cost_basis': None,
                'avco': new_avco, 'gain': 0, 'internal':is_internal, 'total_left':new_total,
                'error': None})

        return

    # ── Same-timestamp merge ──────────────────────────────────────────────
    new_qty   = quantity_n
    new_cost  = quantity_n * price_n
    old_total = 0.0
    old_cost  = 0.0

    while pool and pool[-1][L_DATE] == date:
        _, lot_qty, lot_total, lot_avco = pool.pop()
        new_qty  += lot_qty
        new_cost += lot_qty * lot_avco
        # lot_total includes this lot — subtract to recover pool state before it
        old_total = lot_total - lot_qty
        old_cost  = old_total * lot_avco

    total_quantity = old_total + new_qty
    new_avco       = (old_cost + new_cost) / total_quantity

    pool.append((date, new_qty, total_quantity, new_avco))

    gains.append({**source_row,
                'timestamp': date, 'wallet': wallet,'asset': asset, 'kind': kind,
                'quantity': new_qty, 'price': price_n,
                'proceeds': None, 'cost_basis': None,
                'avco': new_avco, 'gain': 0, 'internal':is_internal, 'total_left':total_quantity,
                'error': None})


# ── Sell ──────────────────────────────────────────────────────────────────────
def process_sell(d30p, graveyard, gains, is_internal, wallet, asset, date, quantity, price,
                 source_row, kind='sell'):
    """
    Steps:
        1. Pop last lot → read avco and total_quantity.
        2. Validate: sell date >= lot date, total_quantity >= sell quantity.
        3. gain = quantity * (price - avco)
        4. Decrement total_quantity, re-append last lot.
        5. FIFO drain from pool[0] forward, stopping before the last lot:
               while len(pool) > 1 and sell_qty >= pool[0][L_QTY]:
                   sell_qty -= pool[0][L_QTY]
                   graveyard.append(pool.popleft())
               partial drain on pool[0] if still remaining
           The last lot is NEVER consumed by the drain — it is the pool state
           carrier (holds current total_quantity and avco).
    """
    pool = d30p[wallet][asset]

    if not pool:
        gains.append({**source_row,
                      'timestamp': date, 'wallet': wallet, 'asset': asset, 'kind': kind,
                      'quantity': quantity, 'price': price,
                      'proceeds': quantity * price, 'cost_basis': 0.0,
                      'avco': 0.0, 'gain': 0.0, 'internal':is_internal,'total_left': None,
                      'error': 'sell with empty pool'})
        return

    lot_date, lot_qty, total_quantity, avco = pool[-1]

    if date < lot_date:
        gains.append({**source_row,
                      'timestamp': date, 'wallet': wallet, 'asset': asset, 'kind': kind,
                      'quantity': quantity, 'price': price,
                      'proceeds': quantity * price, 'cost_basis': 0.0,
                      'avco': avco, 'gain': 0.0,'internal':is_internal, 'total_left':total_quantity - quantity,
                      'error': f'sell date {date} < last lot date {lot_date}'})
        return



    if quantity > total_quantity + 1e-9:
        if is_internal == "NO":
            gains.append({**source_row,
                      'timestamp': date, 'wallet': wallet,'asset': asset, 'kind': kind,
                      'quantity': quantity, 'price': price,
                      'proceeds': total_quantity * price, 'cost_basis': total_quantity*avco,
                      'avco': avco, 'gain': total_quantity*(price-avco),'internal':is_internal, 'total_left':total_quantity - quantity,
                      'error': f'sell qty {quantity:.8f} > pool total {total_quantity:.8f} : all lots sold'})

        elif is_internal == "YES" and kind == 'gas':

            gains.append({**source_row,
                      'timestamp': date, 'wallet': wallet,'asset': asset, 'kind': kind,
                      'quantity': quantity, 'price': price,
                      'proceeds': total_quantity * price, 'cost_basis': total_quantity*avco,
                      'avco': avco, 'gain': total_quantity*(price-avco),'internal':is_internal, 'total_left':total_quantity - quantity,
                      'error': f'sell qty {quantity:.8f} > pool total {total_quantity:.8f} : all lots sold'})


        elif is_internal == "YES" and kind != 'gas':

            gains.append({**source_row,
                      'timestamp': date, 'wallet': wallet,'asset': asset, 'kind': kind,
                      'quantity': quantity, 'price': price,
                      'proceeds': total_quantity * price, 'cost_basis': total_quantity*avco,
                      'avco': avco, 'gain': 0,'internal':is_internal, 'total_left':total_quantity - quantity,
                      'error': f'sell qty {quantity:.8f} > pool total {total_quantity:.8f} : all lots sold'})


        while(pool):

            val=pool.popleft()
            graveyard[wallet][asset].append(val)

        return

    # ── Gain ──────────────────────────────────────────────────────────────
    proceeds   = quantity * price
    cost_basis = quantity * avco
    gain       = proceeds - cost_basis

    if is_internal=="NO":

        gains.append({**source_row,
                    'timestamp': date, 'wallet': wallet,'asset': asset, 'kind': kind,
                    'quantity': quantity, 'price': price,
                    'proceeds': proceeds, 'cost_basis': cost_basis,
                    'avco': avco, 'gain': gain,'internal':is_internal, 'total_left':total_quantity - quantity,
                    'error': None})

    if is_internal=="YES" and kind=='gas':

            gains.append({**source_row,
                    'timestamp': date,'wallet': wallet, 'asset': asset, 'kind': kind,
                    'quantity': quantity, 'price': price,
                    'proceeds': proceeds, 'cost_basis': cost_basis,
                    'avco': avco, 'gain': gain,'internal':is_internal, 'total_left':total_quantity - quantity,
                    'error': None})

    if is_internal=="YES" and kind!='gas':

            gains.append({**source_row,
                    'timestamp': date,'wallet': wallet, 'asset': asset, 'kind': kind,
                    'quantity': quantity, 'price': price,
                    'proceeds': proceeds, 'cost_basis': cost_basis,
                    'avco': avco, 'gain': 0,'internal':is_internal, 'total_left':total_quantity - quantity,
                    'error': None})

    # ── Update total on last lot, re-append ──────────────────────────────
    pool.pop()
    pool.append((lot_date, lot_qty, total_quantity - quantity, avco))

    # ── FIFO drain from pool[0], never consuming the last lot ─────────────
    remaining = quantity
    while remaining > 1e-12 and len(pool) > 1:
        front_date, front_qty, front_total, front_avco = pool[0]
        if remaining >= front_qty - 1e-12:
            remaining -= front_qty
            graveyard[wallet][asset].append(pool.popleft())
        else:
            pool[0] = (front_date, front_qty - remaining, front_total, front_avco)
            remaining = 0.0

    # Partial drain on last lot if still remaining
    if remaining > 1e-12 and pool:
        fd, fq, ft, fa = pool[0]
        pool[0] = (fd, fq - remaining, ft, fa)

    # Sync: L_QTY on the last lot must never exceed L_TOTAL.
    # After a full sell on a single-lot pool, pop/append sets L_TOTAL=0
    # but the drain loop skips the last lot, leaving L_QTY stale.
    if pool:
        fd, fq, ft, fa = pool[-1]
        if fq > ft:
            pool[-1] = (fd, ft, ft, fa)


# ── Gas ───────────────────────────────────────────────────────────────────────
def process_gas(d30p, graveyard, gains, row, source_row, order_type):
    """
    Gas fee = disposal of the fee asset, treated as a sell.
    Only on sell/withdraw/trade — not on buy/deposit.
    """
    if order_type in ('deposit', 'buy'):
        return

    wallet = row.get('source_name')
    fee_asset = row.get('fee_asset_unique_symbol')
    fee_qty   = row.get('fee_volume')
    fee_price = row.get('fee_asset_price_gbp')
    ts        = row.get('timestamp')
    is_internal = row.get('internal_transfer')

    if not (_is_valid(fee_asset) and _is_valid(fee_qty) and _is_valid(fee_price)):
        return

    try:
        qty_f   = float(fee_qty)
        price_f = float(fee_price)
    except (ValueError, TypeError):
        return

    if qty_f <= 0:
        return

    process_sell(d30p, graveyard, gains, is_internal,wallet=str(wallet).strip(),
                 asset=str(fee_asset).strip(),
                 date=ts, quantity=qty_f, price=price_f,
                 source_row=source_row, kind='gas')


# ── Main loop ─────────────────────────────────────────────────────────────────
def run_matching(df: pd.DataFrame,snap):
    d30p      = snap
    graveyard = defaultdict(lambda: defaultdict(deque))
    gains     = []

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
            wallet = row.get('source_name')
            asset = row.get('incoming_asset_unique_symbol')
            qty   = row.get('incoming_volume')
            price = row.get('incoming_asset_price_gbp')
            is_internal = row.get('internal_transfer')

            if _is_valid(wallet) and _is_valid(asset) and _is_valid(qty) and _is_valid(price):
                try:
                    qty_f, price_f = float(qty), float(price)
                    if qty_f > 0:
                        process_buy(d30p, gains, is_internal, str(wallet).strip(), str(asset).strip(), ts, qty_f, price_f,source_row=source_row, kind='buy')
                except (ValueError, TypeError):
                    pass

            process_gas(d30p, graveyard, gains, row, source_row, order_type)

        # ── SELL / WITHDRAWAL ─────────────────────────────────────────────
        elif order_type in ('withdraw', 'withdrawal', 'sell'):
            wallet = row.get('source_name')
            asset = row.get('outgoing_asset_unique_symbol')
            qty   = row.get('outgoing_volume')
            price = row.get('outgoing_asset_price_gbp')
            is_internal=row.get('internal_transfer')

            if _is_valid(wallet) and _is_valid(asset) and _is_valid(qty) and _is_valid(price):
                try:
                    qty_f, price_f = float(qty), float(price)
                    if qty_f > 0:
                        process_sell(d30p, graveyard, gains,is_internal, str(wallet).strip(),
                                     str(asset).strip(), ts, qty_f, price_f,
                                     source_row=source_row, kind='sell')
                except (ValueError, TypeError):
                    pass

            process_gas(d30p, graveyard, gains, row, source_row, order_type)

        # ── TRADE ─────────────────────────────────────────────────────────
        elif order_type == 'trade':
            wallet = row.get('source_name')
            out_asset = row.get('outgoing_asset_unique_symbol')
            out_qty   = row.get('outgoing_volume')
            out_price = row.get('outgoing_asset_price_gbp')

            if _is_valid(wallet) and _is_valid(out_asset) and _is_valid(out_qty) and _is_valid(out_price):
                try:
                    qty_f, price_f = float(out_qty), float(out_price)
                    if qty_f > 0:
                        process_sell(d30p, graveyard, gains, is_internal,str(wallet).strip(),
                                     str(out_asset).strip(), ts, qty_f, price_f,
                                     source_row=source_row, kind='trade_sell')
                except (ValueError, TypeError):
                    pass

            in_asset = row.get('incoming_asset_unique_symbol')
            in_qty   = row.get('incoming_volume')
            in_price = row.get('incoming_asset_price_gbp')

            if _is_valid(wallet) and _is_valid(in_asset) and _is_valid(in_qty) and _is_valid(in_price):
                try:
                    qty_f, price_f = float(in_qty), float(in_price)
                    if qty_f > 0:
                        process_buy(d30p, gains, is_internal, str(wallet).strip(), str(in_asset).strip(), ts, qty_f, price_f,source_row=source_row, kind='trade_buy')
                except (ValueError, TypeError):
                    pass

            process_gas(d30p, graveyard, gains, row, source_row, order_type)

        else:
            continue

    return gains, d30p, graveyard


# ── Pool snapshot ─────────────────────────────────────────────────────────────
def summarise_pools(d30p, graveyard):
    rows = []

    for wallet, assets in d30p.items():
        for asset, pool in assets.items():

            if not pool:
                continue

            last = pool[-1]
            if last[L_TOTAL] <= 0:
                continue

            rows.append({
                'wallet': wallet,
                'asset': asset,
                'total_held': last[L_TOTAL],
                'avco_gbp': last[L_AVCO],
                'book_value_gbp': last[L_TOTAL] * last[L_AVCO],
                'live_lots': len(pool),
                'exhausted_lots': len(
                    graveyard.get(wallet, {}).get(asset, [])
                ),
            })

    return pd.DataFrame(rows)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    df = run(r"C:\Users\Arunjeet\OneDrive - Harris & Trotter LLP\Downloads\keeper_data")

    print("\nRunning AVCO matching...")

    folder_snap = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Arunjeet\OneDrive - Harris & Trotter LLP\Downloads\test_keeper_snap"
    snap = snapshot(folder_snap)

    gains, d30p, graveyard = run_matching(df,snap)

    gains_df = pd.DataFrame(gains)
    print(f"\nGains records : {len(gains_df):,}")
    errors = gains_df[gains_df['error'].notna()] if 'error' in gains_df.columns else pd.DataFrame()
    errors.to_csv(r"errors.csv", index=False)  #ADDED...

    #grave=pd.DataFrame(graveyard)
    #print(graveyard.head(n=5))

    #grave.to_csv(r"sold_lots.csv", index=False)

    if not errors.empty:
        print(f"Rows with errors : {len(errors)}")
        print(errors[['timestamp', 'asset', 'kind', 'quantity', 'error']].to_string())
    print(gains_df.head(20).to_string())
    gains_df.to_csv('gains_avco.csv', index=False)

    pools_df = summarise_pools(d30p, graveyard)
    print(f"\nAssets with non-zero balance : {len(pools_df):,}")
    print(pools_df.to_string())
    pools_df.to_csv('pool_snapshots.csv', index=False)

#-------------------------------------------------------------------------------------------------------------------
