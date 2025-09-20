import os
import json

RESULTS_DIR = "test/results"
ANSWER_FILE = "test/paper_user_match_answers.json"
VERSIONS = [1, 2, 3, 4, 5, 6]
TOTAL_MEMBERS = 29  # 전체 멤버 수

def load_results(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_answers():
    with open(ANSWER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def evaluate():
    answers = load_answers()
    answer_map = {a["paper"]: set(a["matched_users"]) for a in answers}

    summary_table = []
    headers = [
        "Version", "Weights", "Threshold",
        "TP", "FP", "FN", "TN",
        "Correct", "Total",
        "Accuracy", "Precision", "Recall", "F1"
    ]

    for ver in VERSIONS:
        ver_dir = os.path.join(RESULTS_DIR, f"v{ver}")
        if not os.path.exists(ver_dir):
            print(f"[v{ver}] 디렉토리 없음, 스킵")
            continue

        for fname in os.listdir(ver_dir):
            if not fname.endswith(".json"):
                continue

            path = os.path.join(ver_dir, fname)
            results = load_results(path)
            if not results:
                continue

            # weights/threshold 이름 추출
            base = os.path.splitext(fname)[0]  # w37_t4
            weights_tag, thresh_tag = base.split("_")

            TP = FP = FN = TN = 0
            correct = total = 0

            for r in results:
                paper = r["paper"]
                pred_users = set(r.get("matched_users", []))
                true_users = answer_map.get(paper, set())

                if not true_users:
                    continue

                total += 1
                TP_case = pred_users & true_users
                FP_case = pred_users - true_users
                FN_case = true_users - pred_users
                TN_case = TOTAL_MEMBERS - len(TP_case) - len(FP_case) - len(FN_case)

                TP += len(TP_case)
                FP += len(FP_case)
                FN += len(FN_case)
                TN += TN_case

                if TP_case:
                    correct += 1

            acc = round(correct / total, 3) if total > 0 else 0.0
            precision = round(TP / (TP + FP), 3) if (TP + FP) > 0 else 0.0
            recall = round(TP / (TP + FN), 3) if (TP + FN) > 0 else 0.0
            f1 = round((2 * precision * recall) / (precision + recall), 3) if (precision + recall) > 0 else 0.0

            summary_table.append([
                f"v{ver}", weights_tag, thresh_tag,
                TP, FP, FN, TN,
                correct, total,
                acc, precision, recall, f1
            ])

    # 출력
    print("\n=== 📊 Version Evaluation Summary (with TP/FP/FN/TN/F1) ===")
    print("{:<8} {:<8} {:<10} {:<4} {:<4} {:<4} {:<4} {:<7} {:<7} {:<8} {:<9} {:<7} {:<7}".format(*headers))
    for row in summary_table:
        print("{:<8} {:<8} {:<10} {:<4} {:<4} {:<4} {:<4} {:<7} {:<7} {:<8} {:<9} {:<7} {:<7}".format(*row))
    print("============================================================\n")

if __name__ == "__main__":
    evaluate()
