"""Read the human-reviewed sample; report precision only for reviewed merges."""
import argparse
import pandas as pd
import config
from utils import OUTPUTS


def validation_precision(table):
    answers = table["checked_ok"].fillna("").astype(str).str.strip().str.lower()
    allowed = config.VALIDATION_ACCEPTED_TRUE + config.VALIDATION_ACCEPTED_FALSE + [""]
    if not answers.isin(allowed).all():
        raise ValueError("checked_ok must be blank, yes/no, true/false, or 1/0.")
    merged = pd.to_numeric(table["n_source_records"]) > 1
    reviewed = merged & answers.ne("")
    correct = int((reviewed & answers.isin(config.VALIDATION_ACCEPTED_TRUE)).sum())
    total = int(reviewed.sum())
    return {"reviewed_merges": total, "correct_merges": correct,
            "precision": correct / total if total else None,
            "unreviewed_merges": int((merged & ~reviewed).sum())}


def main(path=None):
    table = pd.read_csv(path or OUTPUTS / "validation_sample.csv")
    result = validation_precision(table)
    print(result)
    print("Precision covers reviewed merged stations only; singleton checks and recall need separate field work.")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?")
    main(parser.parse_args().path)
