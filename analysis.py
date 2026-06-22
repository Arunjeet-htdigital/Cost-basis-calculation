import polars as pl
import duckdb

path = r"C:\ProgramData\Reconciliation_design\ad-hoc\keeper\gains_avco.csv"


df = pl.read_csv(path)

print(df.schema)  # Polars equivalent of df.dtypes


query = """
    WITH main AS(
    SELECT
        substring(timestamp, 1, 7)        AS month,
        wallet,
        asset,
        kind,
        MAX(source_idx)                   AS id,
        COUNT(source_idx)                 AS total,
        SUM(quantity)                     AS total_quantity,
        SUM(proceeds)                     AS total_proceeds,
        SUM(cost_basis)                   AS total_cost_basis,
        MAX(avco)                         AS max_avco,
        SUM(gain)                         AS total_gain,
        COUNT(error)                      AS error_count
    FROM df
    GROUP BY month, wallet, asset, kind
    ORDER BY month, wallet, asset, kind),

    vault as(

    SELECT A.* FROM(
    SELECT substring(timestamp, 1, 7) as month, source_idx, total_left, ROW_NUMBER() OVER (PARTITION BY substring(timestamp, 1, 7), wallet, asset ORDER BY source_idx DESC) AS r from df
    )AS A
    WHERE A.r=1
    )

    select main.*, vault.total_left from main join vault on main.id=vault.source_idx
    ORDER BY month, wallet, asset, kind
    
"""
result = duckdb.sql(query).pl()  # .pl() returns a Polars dataframe
print(result)
result.write_csv(r"analysis.csv")