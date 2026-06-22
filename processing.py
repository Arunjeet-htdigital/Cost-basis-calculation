from extraction import run
import sys


folder = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Arunjeet\OneDrive - Harris & Trotter LLP\Downloads\test_keeper"
df = run(folder)

print(df["timestamp"].unique())
print(df)
print(len(df))



