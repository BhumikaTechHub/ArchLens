import requests
import json
import time


API_URL = "http://127.0.0.1:8000/ask"


TEST_CASES = [

    {
        "question":
            "How is payment processed?",
        "expected_files": [
            "payment.py"
        ],
        "expected_names": [
            "process_payment"
        ]
    },

    {
        "question":
            "Where is the order saved?",
        "expected_files": [
            "database.py"
        ],
        "expected_names": [
            "save_order"
        ]
    },

    {
        "question":
            "When is the customer notified?",
        "expected_files": [
            "notification.py"
        ],
        "expected_names": [
            "send_notification"
        ]
    },

    {
        "question":
            "What happens when an order is created?",
        "expected_files": [
            "order_service.py"
        ],
        "expected_names": [
            "create_order"
        ]
    },

    {
        "question":
            "How is an order cancelled?",
        "expected_files": [
            "order_service.py"
        ],
        "expected_names": [
            "cancel_order"
        ]
    }
]


def run_test(test):

    start = time.perf_counter()

    response = requests.post(
        API_URL,
        json={
            "question":
                test["question"]
        },
        timeout=600
    )

    latency = (
        time.perf_counter()
        - start
    )

    response.raise_for_status()

    data = response.json()

    retrieved = data.get(
        "retrieved_context",
        []
    )

    text = json.dumps(
        retrieved
    ).lower()


    file_hit = any(
        file.lower() in text
        for file in test["expected_files"]
    )

    name_hit = any(
        name.lower() in text
        for name in test["expected_names"]
    )

    passed = (
        file_hit
        and
        name_hit
    )

    return {
        "question": test["question"],
        "file_hit": file_hit,
        "name_hit": name_hit,
        "passed": passed,
        "latency_seconds": round(
            latency,
            3
        )
    }


def main():

    results = []

    print("\nRETRIEVAL QUALITY EVALUATION")
    print("=" * 50)

    for test in TEST_CASES:

        try:

            result = run_test(
                test
            )

            results.append(
                result
            )

            status = (
                "PASS"
                if result["passed"]
                else "FAIL"
            )

            print(
                f"[{status}] "
                f"{result['question']}"
            )

            print(
                f"       Latency: "
                f"{result['latency_seconds']} sec"
            )

        except Exception as e:

            print(
                f"[ERROR] "
                f"{test['question']}"
            )

            print(
                f"        {e}"
            )


    successful = sum(
        r["passed"]
        for r in results
    )

    total = len(results)

    retrieval_accuracy = (
        successful / total * 100
        if total
        else 0
    )

    print("\nResults")
    print("-" * 50)

    print(
        f"Successful retrievals: "
        f"{successful}/{total}"
    )

    print(
        f"Retrieval Quality: "
        f"{retrieval_accuracy:.2f}%"
    )


    with open(
        "evaluation/retrieval_results.json",
        "w"
    ) as f:

        json.dump(
            {
                "total": total,
                "successful": successful,
                "retrieval_quality":
                    retrieval_accuracy,
                "results": results
            },
            f,
            indent=2
        )


if __name__ == "__main__":
    main()
