import pandas as pd
df=pd.read_csv(r"gains_result.csv")

print(df['gain'].describe())