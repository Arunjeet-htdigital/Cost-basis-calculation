import polars as pl
import duckdb

path = r"C:\ProgramData\Reconciliation_design\ad-hoc\keeper\gains_avco.csv"

pl.Config.set_tbl_rows(20)       # number of rows to display
pl.Config.set_tbl_cols(20)       # number of columns to display
pl.Config.set_tbl_width_chars(200)  # widen table display
pl.Config.set_fmt_str_lengths(100)  # prevent string truncation


df = pl.read_csv(path)

print(df.head(n=10))

