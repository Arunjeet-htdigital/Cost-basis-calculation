import os
import csv
import pandas as pd

   
def checks(df):
    """Find 'currency' in the df and return data from that row onwards."""
    
    for i, row in df.iterrows():
        if row.astype(str).str.contains("currency", case=False, na=False).any():
            new_header = df.iloc[i]
            new_df = df.iloc[i + 1:].reset_index(drop=True)
            new_df.columns = new_header
            new_df.columns = new_df.columns.str.strip().str.lower().str.replace(r'\s+', '_', regex=True)

            # --- Timestamp: split date and time ---
            split_dt = new_df['timestamp'].astype(str).str.strip().str.split(' ', n=1, expand=True)
            raw_date = split_dt[0]
            new_df['time'] = split_dt[1] if split_dt.shape[1] > 1 else None

            # --- Split date into components ---
            temp = raw_date.str.split(r'[/-]', expand=True)
            temp.columns = ['a', 'b', 'c']

            # --- Resolve day/month/year positions ---
            for val in list(temp['b']):
                if val is not None and pd.notna(val) and int(val) > 12:
                    temp['a'], temp['b'] = temp['b'].copy(), temp['a'].copy()
                    break

            t1 = list(temp['c'])
            t2 = list(temp['b'])

            for ind, j in enumerate(t1):
                if j and len(j) == 2:
                    t1[ind], t2[ind] = t2[ind], t1[ind]
            temp['c'] = t1
            temp['b'] = t2

            # --- Concat as yyyy-mm-dd ---
            new_df['date'] = pd.to_datetime(temp['c'] + '-' + temp['b'] + '-' + temp['a'])

            # --- Drop original timestamp ---
            new_df.drop(columns=['timestamp'], inplace=True)

            # --- Price conversion ---
            new_df['price'] = pd.to_numeric(
                new_df['price'].astype(str).str.replace(r'[,$£€\s]', '', regex=True),
                errors='coerce'
            ).astype(float)
            
            # --- Recreate timestamp from date and time ---
            new_df['timestamp'] = pd.to_datetime(
                new_df['date'].astype(str) + ' ' + new_df['time'].astype(str),
                errors='coerce'
            )

            # --- Drop date and time, keep only timestamp ---
            new_df.drop(columns=['date', 'time'], inplace=True)

            # --- Reorder: timestamp first ---
            cols = ['timestamp'] + [c for c in new_df.columns if c != 'timestamp']
            new_df = new_df[cols]

            return new_df
    
    return df


def read(FOLDER_PATH, global_df):
    for filename in os.listdir(FOLDER_PATH):
        if filename.endswith(".csv"):
            filepath = os.path.join(FOLDER_PATH, filename)
            
            with open(filepath, mode="r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            df = checks(pd.DataFrame(rows))
            df["source_file"] = filename
            
            global_df = pd.concat([global_df, df], ignore_index=True)

    return global_df
