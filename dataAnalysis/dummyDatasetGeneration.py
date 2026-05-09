"""
Generate dummy evaluation dataset and save to dummyDataset.json.
"""

import json
import numpy as np
import pandas as pd

np.random.seed(42)

METRICS = ["Safety", "Naturalness", "Responsiveness", "Predictability", "Comfort"]
N = 50

# Auto Evaluator and Human (Random Population) have similar grading patterns.
# Human (Robotics Students) grade more strictly: they know what good navigation
# looks like, so they set a higher bar — resulting in consistently lower scores.
GROUP_CONFIGS = {
    "Auto Evaluator":            {"loc": 6.9, "scale": 1.1},
    "Human (Random Population)": {"loc": 6.8, "scale": 1.3},
    "Human (Robotics Students)": {"loc": 5.4, "scale": 0.9},
}


def generate_group(loc: float, scale: float) -> pd.DataFrame:
    data = {}
    for metric in METRICS:
        scores = np.clip(
            np.random.normal(loc=loc, scale=scale, size=N),
            0, 10
        )
        data[metric] = scores
    df = pd.DataFrame(data)
    df["Global"] = df.mean(axis=1)
    return df


def main():
    dataset = {}
    for group_name, cfg in GROUP_CONFIGS.items():
        df = generate_group(**cfg)
        dataset[group_name] = df.to_dict(orient="list")

    with open("dummyDataset.json", "w") as f:
        json.dump(dataset, f, indent=2)

    print("Dataset saved to dummyDataset.json")
    for group_name, df_dict in dataset.items():
        df = pd.DataFrame(df_dict)
        print(f"  {group_name}: {len(df)} samples, "
              f"Global mean={df['Global'].mean():.2f}")


if __name__ == "__main__":
    main()
