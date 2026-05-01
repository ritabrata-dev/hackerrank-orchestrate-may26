import pandas as pd
import sys
from agent import process_ticket


def get_first_present(row, keys):
    for key in keys:
        value = row.get(key, "")
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def run(input_path, output_path):
    df = pd.read_csv(input_path)
    results = []

    for i, row in df.iterrows():
        issue = get_first_present(row, ["issue", "Issue", "subject", "Subject"])
        company = get_first_present(row, ["company", "Company"])

        print(f"Processing ticket {i+1}...")

        try:
            result = process_ticket(issue, company)
        except Exception as e:
            result = {
                "status": "escalated",
                "product_area": "error",
                "request_type": "invalid",
                "response": "An error occurred. Escalating to human support.",
                "justification": str(e)
            }

        results.append(result)

    pd.DataFrame(results).to_csv(output_path, index=False)
    print(f"\nDone. Output saved to {output_path}")

if __name__ == "__main__":
    input_csv = sys.argv[1] if len(sys.argv) > 1 else "../support_tickets/support_tickets.csv"
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "../support_tickets/output.csv"
    run(input_csv, output_csv)