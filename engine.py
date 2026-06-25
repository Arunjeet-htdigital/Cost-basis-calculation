import pandas as pd
from collections import defaultdict, deque
import pandas as pd


df=pd.read_csv(r"total_data.csv",low_memory=False)

df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df['price'] = pd.to_numeric(df['price'], errors='coerce').astype(float)

for col in df.columns:
    if col not in ('timestamp', 'price'):
        df[col] = df[col].astype(str).str.strip()

BUY_TYPES  = {'buy','cross chain buy','airdrop','income','interest',
               'staking reward','mining','bridge in','incoming',
               'dust in','receive receipt token','add liquidity','loan','mint'}
SELL_TYPES = {'sell','cross chain sell','bridge out','outgoing','dust out',
               'burn','expense','loan repayment','loan fee'}

def clean_number(val):
    if pd.isna(val): return 0.0
    return float(str(val).replace(',','').strip())

# --- Prep ---
df['_trade_clean'] = df['trade_type'].str.strip().str.lower()
df['_is_sell']     = df['_trade_clean'].isin(SELL_TYPES).astype(int)
df['_qty']         = df['quantity'].apply(clean_number)
df['_price']       = df['price'].apply(clean_number)
df['_date']        = pd.to_datetime(df['timestamp']).dt.normalize()
is_sell            = df['_is_sell'].astype(bool)

d0        = defaultdict(deque)            # same-day buy buffer
d30       = defaultdict(deque)            # parked sells awaiting match
d30p      = defaultdict(deque)            # Section 104 pool
gains     = []
last_date = defaultdict(lambda: None)


def s104_total_qty(asset):
    return sum(l[1] for l in d30p[asset])


def s104_append(asset, date, qty, price):
    """Lazy AVCO — only last element holds running AVCO."""
    if d30p[asset]:
        pq = s104_total_qty(asset)
        la = d30p[asset][-1][2]
        d30p[asset].append([date, qty, (pq * la + qty * price) / (pq + qty)])
    else:
        d30p[asset].append([date, qty, price])


def s104_sell(asset, sell_qty, sell_price):
    """AVCO price from last element, FIFO qty drain from front."""
    if not d30p[asset]: return 0.0
    avco      = d30p[asset][-1][2]
    remaining = sell_qty
    gain      = 0.0
    while remaining > 0 and d30p[asset]:
        lot = d30p[asset][0]
        q   = lot[1]
        if q > remaining:
            lot[1]   -= remaining
            gain     += remaining * (sell_price - avco)
            remaining = 0
        else:
            d30p[asset].popleft()
            gain     += q * (sell_price - avco)
            remaining -= q
    return gain


def close_matched(asset, rule_label):
    """Record and remove fully consumed sells."""
    rem = deque()
    for sell in d30[asset]:
        if sell[1] <= 0:
            gains.append({'date': sell[0], 'asset': asset,
                          'gain': round(sell[4], 2), 'rule': rule_label})
        else:
            rem.append(sell)
    d30[asset] = rem


def flush_d0(asset, flush_date):
    """
    Day boundary — pop() from d0 tail (LIFO within day),
    match against same-day parked sells, route remainder to s104.
    """
    while d0[asset]:
        b_date, b_qty, b_price = d0[asset].pop()
        available = b_qty

        for sell in d30[asset]:
            if available <= 0: break
            if sell[0] == b_date and sell[1] > 0:
                matched    = min(available, sell[1])
                sell[4]   += matched * (sell[3] - b_price)
                sell[1]   -= matched
                available -= matched

        close_matched(asset, 'same_day')

        if available > 0:
            s104_append(asset, b_date, available, b_price)


def flush_expired(asset, current_date):
    """Expire sells outside 30-day window → split B&B accrued + s104 remainder."""
    while True:
        if not d30[asset]: break
        if (current_date - d30[asset][0][0]).days > 30:
            s_date, s_qty, s_tot, s_price, s_gain = d30[asset].popleft()
            if s_gain > 0:
                gains.append({'date': s_date, 'asset': asset,
                              'gain': round(s_gain, 2), 'rule': 'bed_and_breakfast'})
            if s_qty > 0:
                gains.append({'date': s_date, 'asset': asset,
                              'gain': round(s104_sell(asset, s_qty, s_price), 2),
                              'rule': 'section_104'})
        else:
            break


# --- Main loop ---
for idx, row in df.iterrows():
    asset = row['currency']
    date  = row['_date']
    qty   = row['_qty']
    price = row['_price']
    tt    = row['_trade_clean']

    if tt not in BUY_TYPES and tt not in SELL_TYPES:
        continue

    # Day boundary — flush d0 buffer and expire stale sells
    if last_date[asset] is not None and date != last_date[asset]:
        flush_d0(asset, last_date[asset])
        flush_expired(asset, date)

    last_date[asset] = date

    if is_sell[idx]:
        d30[asset].append([date, qty, qty, price, 0.0])

    else:
        # B&B — match against older parked sells immediately
        available = qty
        for sell in d30[asset]:
            if available <= 0: break
            if sell[0] != date and sell[1] > 0:
                matched    = min(available, sell[1])
                sell[4]   += matched * (sell[3] - price)
                sell[1]   -= matched
                available -= matched
        close_matched(asset, 'bed_and_breakfast')

        # Buffer remainder in d0 for same-day matching at day boundary
        if available > 0:
            d0[asset].append((date, available, price))


# --- Final flush ---
for asset in list(d0.keys()):
    flush_d0(asset, last_date[asset])

for asset, dq in list(d30.items()):
    while dq:
        s_date, s_qty, s_tot, s_price, s_gain = dq.popleft()
        if s_gain > 0:
            gains.append({'date': s_date, 'asset': asset,
                          'gain': round(s_gain, 2), 'rule': 'bed_and_breakfast'})
        if s_qty > 0:
            gains.append({'date': s_date, 'asset': asset,
                          'gain': round(s104_sell(asset, s_qty, s_price), 2),
                          'rule': 'section_104'})

# --- Output ---
gains_df = pd.DataFrame(gains).sort_values(['date','asset']).reset_index(drop=True)
df.drop(columns=['_is_sell','_trade_clean','_qty','_price','_date'], inplace=True)
gains_df.to_csv(r"gains_result.csv", index=False)