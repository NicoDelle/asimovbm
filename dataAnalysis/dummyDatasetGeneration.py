"""
Generate dummy evaluation dataset and save to dummyDataset.json.
Scores are on the 0-100 scale defined in docs/specs/social-navigation-metrics.md.

Macro metrics:
  - Perceived Dexterity   (TSR, completion time, path efficiency)
  - Perceived Safety      (min distance, proxemic intrusion, speed near humans)
  - Perceived Social Awareness (gesture response, acknowledgement, human-aware approach)
  - Impression            (motion smoothness SPARC, stability, morphology-task fit)
"""

import json
from collections.abc import Sequence
import numpy as np
import pandas as pd

np.random.seed(42)

METRICS = [
    "Perceived Dexterity",
    "Perceived Safety",
    "Perceived Social Awareness",
    "Impression",
]

N = 50  # evaluations per group

# Auto Evaluator and Human (Random Population) score similarly.
# Human (Robotics Students) are stricter: they set a higher bar because
# they know what good social navigation looks like, so they score lower.
GROUP_CONFIGS = {
    "Auto Evaluator": {
        "loc":   [70, 68, 65, 72],   # per-metric means
        "scale": [10, 11,  9, 10],
    },
    "Human (Random Population)": {
        "loc":   [69, 67, 63, 71],
        "scale": [12, 13, 11, 12],
    },
    "Human (Robotics Students)": {
        "loc":   [55, 52, 48, 57],   # stricter graders
        "scale": [ 9,  9,  8,  8],
    },
}


def generate_group(loc: Sequence[int | float], scale: Sequence[int | float]) -> pd.DataFrame:
    data = {}
    for metric, m, s in zip(METRICS, loc, scale):
        scores = np.clip(np.random.normal(loc=m, scale=s, size=N), 0, 100)
        data[metric] = scores
    df = pd.DataFrame(data)
    df["Composite"] = df.mean(axis=1)
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
        print(f"  {group_name}: Composite mean={df['Composite'].mean():.1f}  "
              f"std={df['Composite'].std():.1f}")


if __name__ == "__main__":
    main()
