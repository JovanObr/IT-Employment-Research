import pandas as pd
a = pd.read_csv("data/raw/census_acs1_metro.csv", dtype={"cbsa_code": str})
for y in (2019, 2024):
    d = a[a.year == y]
    print(y, len(d), "areas | workers missing:", d.workers.isna().sum(), "| workers_home missing:", d.workers_home.isna().sum())