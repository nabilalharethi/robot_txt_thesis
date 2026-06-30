import pandas as pd
from scipy import stats

# Load your results CSV
df = pd.read_csv("log/raw_results.csv")

# Remove ERROR rows
df = df[df["strategy"] != "ERROR"].copy()

# Drop rows where either value is missing
df = df.dropna(subset=["conflict_count", "compliance_score"])

conflicts = df["conflict_count"]
score = df["compliance_score"]

# Pearson's r
pearson_r, pearson_p = stats.pearsonr(conflicts, score)

# Spearman's rho
spearman_r, spearman_p = stats.spearmanr(conflicts, score)

print(f"Pearson r = {pearson_r:.4f}, p = {pearson_p:.4f}")
print(f"Spearman rho = {spearman_r:.4f}, p = {spearman_p:.4f}")