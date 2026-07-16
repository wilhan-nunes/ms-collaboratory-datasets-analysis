import requests
import pandas as pd

params = {
    "pageSize": 3000,
    "offset": 0,
    "query": '{"keywords_input":"mscollaboratory"}',
}
r = requests.get("https://massive.ucsd.edu/ProteoSAFe/QueryDatasets", params=params)
datasets = r.json()["row_data"]
df = pd.DataFrame(datasets)
print(df[["dataset", "title"]].head())