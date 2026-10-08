import requests
import json
import time


API_URL = "http://127.0.0.1:8000/ask"


SUPPORTED_CASES = [

    {
        "question":
            "What functions are called when an order is created?",

        "required_terms": [
            "create_order",
            "save_order",
            "process_payment",
            "send_notification"
        ]
    },

    {
        "question":
            "Where is the order saved?",

        "required_terms": [
            "save_order"
        ]
    },

    {
        "question":
            "How is payment processed?",

        "required_terms": [
            "process_payment"
        ]
    },

    {
        "question":
            "When is the customer notified?",

        "required_terms": [
            "send_notification"
            
        ]
    }
]


UNSUPPORTED_CASES = [

    {
        "question":
            "How does the repository handle employee payroll?"
    },

    {
        "question":
            "Does the system support employee authentication?"
    }
]


def ask(question):

    start = time.perf_counter()

    response = requests.post(
        API_URL,
        json={
            "question": question
        },
        timeout=600
    )

    latency = (
        time.perf_counter()
        - start
    )

    response.raise_for_status()

    data = response.json()

    return (
        data.get("answer", ""),
        latency
    )


def supported_test(case):

    answer, latency = ask(
        case["question"]
    )

    answer_lower = answer.lower()

    missing = []

    for term in case["required_terms"]:

        if term.lower() not in answer_lower:

            missing.append(term)

    passed = (
        len(missing) == 0
    )

    return {
        "question": case["question"],
        "passed": passed,
        "missing_terms": missing,
        "latency_seconds": round(
            latency,
            3
        )
    }


def unsupported_test(case):

    answer, latency = ask(
        case["question"]
    )

    answer_lower = answer.lower()

    refusal_phrases = [
        "don't have enough information",
        "do not have enough information",
        "not enough information",
        "not available",
        "cannot determine",
        "can't determine"
    ]

    refused = any(
        phrase in answer_lower
        for phrase in refusal_phrases
    )

    return {
        "question": case["question"],
        "refused": refused,
        "hallucination":
            not refused,
        "latency_seconds": round(
            latency,
            3
        )
    }


def main():

    supported_results = []
    unsupported_results = []


    print(
        "\nHALLUCINATION EVALUATION"
    )

    print("=" * 50)


    print(
        "\nSupported questions"
    )


    for case in SUPPORTED_CASES:

        try:

            result = supported_test(
                case
            )

            supported_results.append(
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

            if result["missing_terms"]:

                print(
                    "       Missing:",
                    result["missing_terms"]
                )

        except Exception as e:

            print(
                f"[ERROR] "
                f"{case['question']}"
            )

            print(e)


    print(
        "\nUnsupported questions"
    )


    for case in UNSUPPORTED_CASES:

        try:

            result = unsupported_test(
                case
            )

            unsupported_results.append(
                result
            )

            status = (
                "PASS"
                if result["refused"]
                else "HALLUCINATION"
            )

            print(
                f"[{status}] "
                f"{result['question']}"
            )

        except Exception as e:

            print(
                f"[ERROR] "
                f"{case['question']}"
            )

            print(e)


    hallucinations = sum(
        r["hallucination"]
        for r in unsupported_results
    )

    total_unsupported = len(
        unsupported_results
    )

    hallucination_rate = (
        hallucinations
        / total_unsupported
        * 100
        if total_unsupported
        else 0
    )


    print("\nResults")
    print("-" * 50)

    print(
        "Unsupported questions:",
        total_unsupported
    )

    print(
        "Hallucinations:",
        hallucinations
    )

    print(
        f"Hallucination Rate: "
        f"{hallucination_rate:.2f}%"
    )


    with open(
        "evaluation/hallucination_results.json",
        "w"
    ) as f:

        json.dump(
            {
                "hallucination_rate":
                    hallucination_rate,

                "supported":
                    supported_results,

                "unsupported":
                    unsupported_results
            },
            f,
            indent=2
        )


if __name__ == "__main__":
    main()
