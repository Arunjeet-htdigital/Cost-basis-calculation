from extraction import read
import pandas as pd

FOLDER_PATH = r"C:\Users\Arunjeet\OneDrive - Harris & Trotter LLP\Downloads\tax_gl"  # <-- change this

global_df = pd.DataFrame()


df=read(FOLDER_PATH, global_df)
exclude = [
    'spam',
    'ignore out',
    'ignore in',
    'failed out',
    'failed in',
    'fiat withdrawal',
    'fiat deposit',
    'realized profit',
    'realized loss',
    'transfer in',
    'transfer out',
    'spam out'
]

new_df = df[~df['trade_type'].str.strip().str.lower().isin(exclude)][:1000]

new_df.to_csv(r"total_data.csv", index=False)
print(new_df.describe())
