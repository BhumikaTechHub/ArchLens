import requests
import time
import statistics


API_URL = "http://127.0.0.1:8000/ask"


QUESTIONS = [
    "What happens when an order is created?",
    "How is payment processed?",
    "Where is the order saved?",
    "When is the customer notified?",
    "How is an order cancelled?"
]


def main():

    latencies = []

    print("\nLATENCY EVALUATION")
    print("=" * 50)


    for question in QUESTIONS:

        start = time.perf_counter()

        try:

            response = requests.post(
                API_URL,
                json={
                    "question": question
                },
                timeout=600
            )

            response.raise_for_status()

            elapsed = (
                time.perf_counter()
                - start
            )

            latencies.append(
                elapsed
            )

            print(
                f"{elapsed:.2f}s - "
                f"{question}"
            )

        except Exception as e:

            print(
                f"ERROR - {question}"
            )

            print(e)


    if not latencies:

        print(
            "\nNo successful requests."
        )

        return


    average = statistics.mean(
        latencies
    )

    minimum = min(
        latencies
    )

    maximum = max(
        latencies
    )


    print("\nResults")
    print("-" * 50)

    print(
        f"Average latency: "
        f"{average:.2f} seconds"
    )

    print(
        f"Minimum latency: "
        f"{minimum:.2f} seconds"
    )

    print(
        f"Maximum latency: "
        f"{maximum:.2f} seconds"
    )


if __name__ == "__main__":
    main()
