import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from git import Repo
from git.exc import GitCommandError


BASE_DIR = Path(__file__).resolve().parent.parent

REPOSITORIES_DIR = (
    BASE_DIR / "imported_repositories" / "repositories"
)

METADATA_DIR = (
    BASE_DIR / "imported_repositories" / "metadata"
)


def validate_github_url(url):
    """Validate and normalize a public GitHub repository URL."""

    if not isinstance(url, str):
        raise ValueError("Repository URL must be a string.")

    url = url.strip()
    parsed = urlparse(url)

    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username
        or parsed.password
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Only public HTTPS GitHub repository URLs are supported."
        )

    parts = parsed.path.strip("/").split("/")

    if len(parts) != 2:
        raise ValueError(
            "Invalid URL. Expected: https://github.com/owner/repository"
        )

    owner, repository = parts

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner):
        raise ValueError("Invalid GitHub owner name.")

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository name.")

    if owner in {".", ".."} or repository in {".", ".."}:
        raise ValueError("Invalid repository path.")

    repository = repository.removesuffix(".git")

    if not repository:
        raise ValueError("Repository name cannot be empty.")

    normalized_url = (
        f"https://github.com/{owner}/{repository}.git"
    )

    repo_id = f"gh_{owner}_{repository}".lower()

    return {
        "owner": owner,
        "repository": repository,
        "repository_id": repo_id,
        "url": normalized_url
    }


def import_repository(url):
    """Clone and register a public GitHub repository."""

    details = validate_github_url(url)

    repo_id = details["repository_id"]

    REPOSITORIES_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    repo_path = REPOSITORIES_DIR / repo_id
    metadata_path = METADATA_DIR / f"{repo_id}.json"

    if repo_path.exists() or metadata_path.exists():
        raise ValueError(
            f"Repository '{repo_id}' has already been imported."
        )

    try:
        print(f"Cloning {details['url']}")

        Repo.clone_from(
            details["url"],
            str(repo_path),
            depth=1,
            multi_options=["--no-recurse-submodules"]
        )

        repository = Repo(repo_path)

        metadata = {
            "repository_id": repo_id,
            "owner": details["owner"],
            "repository_name": details["repository"],
            "source_url": details["url"],
            "local_path": str(
                repo_path.relative_to(BASE_DIR)
            ),
            "status": "cloned",
            "commit": repository.head.commit.hexsha,
            "imported_at": datetime.now(
                timezone.utc
            ).isoformat()
        }

        metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8"
        )

        print("Repository cloned successfully.")

        return metadata

    except Exception as error:

        # Remove only the incomplete clone created by this operation.
        if repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)

        if isinstance(error, GitCommandError):
            raise RuntimeError(
                f"Git clone failed: {error}"
            ) from error

        raise


def list_imported_repositories():
    """Return metadata for successfully imported repositories."""

    if not METADATA_DIR.exists():
        return []

    repositories = []

    for metadata_file in METADATA_DIR.glob("gh_*.json"):

        try:
            metadata = json.loads(
                metadata_file.read_text(encoding="utf-8")
            )

            repo_path = BASE_DIR / metadata["local_path"]

            if repo_path.is_dir():
                repositories.append(metadata)

        except (OSError, ValueError, KeyError):
            continue

    return repositories
