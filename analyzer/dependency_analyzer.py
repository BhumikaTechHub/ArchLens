import json
from collections import defaultdict


ANALYSIS_FILE = "analysis.json"


def analyze_dependencies():

    with open(ANALYSIS_FILE, "r") as f:
        analysis = json.load(f)

    dependencies = defaultdict(list)

    for file_info in analysis:

        file_path = file_info["file"]

        for imported in file_info.get("imports", []):

            dependencies[file_path].append(imported)

    return dependencies


def main():

    dependencies = analyze_dependencies()

    print("\nARCHITECTURE DEPENDENCIES\n")

    for file_path, modules in dependencies.items():

        print(file_path)

        if not modules:
            print("  └── No dependencies")
            continue

        for module in modules:

            print(
                f"  └── depends on → {module}"
            )


if __name__ == "__main__":
    main()
