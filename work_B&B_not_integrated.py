import pandas as pd
df=pd.read_csv(r"total_data.csv",low_memory=False)

df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df['price'] = pd.to_numeric(df['price'], errors='coerce').astype(float)

for col in df.columns:
    if col not in ('timestamp', 'price'):
        df[col] = df[col].astype(str).str.strip()

print(df['trade_type'].unique())


from collections import deque
import pandas as pd

holdings = {}
realised = {}

def get_holdings(currency):
    if currency not in holdings:
        holdings[currency] = {'d0': deque(), 'd30': deque(), 'd30p': deque()}
    return holdings[currency]

def get_realised(currency):
    if currency not in realised:
        realised[currency] = []
    return realised[currency]

def avco(stack: deque):
    if not stack:
        return 0.0
    return sum(lot['price'] for lot in stack) / len(stack)


def promote_lots(currency, current_ts: pd.Timestamp):
    stacks = get_holdings(currency)

    # Promote d0 → d30
    remaining_d0 = deque()
    for lot in stacks['d0']:
        age = (current_ts - lot['timestamp']).days
        if age > 0:
            stacks['d30'].append(lot)
        else:
            remaining_d0.append(lot)
    stacks['d0'] = remaining_d0

    # Promote d30 → d30p
    remaining_d30 = deque()
    for lot in stacks['d30']:
        age = (current_ts - lot['timestamp']).days
        if age > 30:
            stacks['d30p'].append(lot)
        else:
            remaining_d30.append(lot)
    stacks['d30'] = remaining_d30


def add_buy(currency, quantity, price, timestamp):
    stacks = get_holdings(currency)
    stacks['d0'].append({
        'quantity':  quantity,
        'price':     price,
        'timestamp': timestamp
    })


def process_sell(currency, sell_qty, sell_price, sell_ts):
    stacks = get_holdings(currency)
    promote_lots(currency, sell_ts)

    remaining     = sell_qty
    lots_consumed = []
    total_price   = 0.0

    for stack_name in ['d0', 'd30', 'd30p']:
        stack = stacks[stack_name]
        if remaining <= 0:
            break

        stack_avco = avco(stack)

        while stack and remaining > 0:
            lot = stack[0]

            if lot['quantity'] <= remaining:
                consumed_qty = lot['quantity']
                stack.popleft()
            else:
                consumed_qty = remaining
                lot['quantity'] -= consumed_qty

            remaining   -= consumed_qty
            total_price += lot['price']

            lots_consumed.append({
                'stack':         stack_name,
                'quantity':      consumed_qty,
                'buy_price':     lot['price'],
                'buy_timestamp': lot['timestamp']
            })

    sold_qty       = sell_qty - remaining
    avco_buy_price = total_price / len(lots_consumed) if lots_consumed else 0.0
    gain           = (sell_price - avco_buy_price) * sold_qty

    record = {
        'timestamp':      sell_ts,
        'currency':       currency,
        'quantity_sold':  sold_qty,
        'sell_price':     sell_price,
        'lots_consumed':  lots_consumed,
        'avco_buy_price': avco_buy_price,
        'realised_gain':  gain,
        'status':         'open'
    }

    get_realised(currency).append(record)
    return record
    
def clean_number(val):
    if pd.isna(val):
        return 0.0
    return float(str(val).replace(',', '').strip())

def process_buy_after_sell(currency, buy_qty, buy_price, buy_ts):
    for disposal in get_realised(currency):
        if disposal['status'] != 'open':
            continue

        delta = (buy_ts - disposal['timestamp']).days

        if delta > 30:
            disposal['status'] = 'closed'
            continue

        all_prices    = [lc['buy_price'] for lc in disposal['lots_consumed']] + [buy_price]
        new_avco      = sum(all_prices) / len(all_prices)

        disposal['avco_buy_price'] = new_avco
        disposal['realised_gain']  = (disposal['sell_price'] - new_avco) * disposal['quantity_sold']
        disposal['status']         = 'repriced'

    add_buy(currency, buy_qty, buy_price, buy_ts)


def process_transactions(df):
    # --- Remove transfers entirely ---
    transfer_mask = df['trade_type'].str.lower().str.contains('transfer')
    df = df[~transfer_mask].copy()

    df = df.sort_values('timestamp').reset_index(drop=True)

    for _, row in df.iterrows():
        currency   = row['currency']
        trade_type = row['trade_type'].lower()
        price    = clean_number(row['price'])
        quantity = clean_number(row['quantity'])
        ts         = row['timestamp']

        is_sell = 'sell' in trade_type

        if is_sell:
            process_sell(currency, quantity, price, ts)
        else:
            if currency in realised and any(r['status'] == 'open' for r in realised[currency]):
                process_buy_after_sell(currency, buy_qty=quantity, buy_price=price, buy_ts=ts)
            else:
                add_buy(currency, quantity, price, ts)

    return df


# --- Run ---
processed_df = process_transactions(df)

# --- Flatten realised gains ---
records = []
for currency, disposals in realised.items():
    for d in disposals:
        records.append({
            'timestamp':      d['timestamp'],
            'currency':       d['currency'],
            'quantity_sold':  d['quantity_sold'],
            'sell_price':     d['sell_price'],
            'avco_buy_price': d['avco_buy_price'],
            'realised_gain':  d['realised_gain'],
            'status':         d['status']
        })

realised_df = pd.DataFrame(records).sort_values('timestamp').reset_index(drop=True)
print(realised_df)
