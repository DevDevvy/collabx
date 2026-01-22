from __future__ import annotations

import secrets
import time
from typing import Dict, Optional, Tuple

from rich.console import Console

from collabx.deploy.shell import run

console = Console()


def _get_project(explicit_project: Optional[str]) -> str:
    if explicit_project:
        return explicit_project
    r = run(["gcloud", "config", "get-value", "project"], check=True)
    proj = (r.out or "").strip()
    if not proj or proj == "(unset)":
        raise RuntimeError("No gcloud project set. Run: gcloud config set project <PROJECT_ID>")
    return proj


def _ensure_services(project: str) -> None:
    run(
        [
            "gcloud",
            "services",
            "enable",
            "run.googleapis.com",
            "cloudbuild.googleapis.com",
            "artifactregistry.googleapis.com",
            "--project",
            project,
            "--quiet",
        ],
        check=False,
    )


def _ensure_repo(project: str, region: str, repo: str) -> None:
    run(
        [
            "gcloud",
            "artifacts",
            "repositories",
            "create",
            repo,
            "--repository-format=docker",
            "--location",
            region,
            "--project",
            project,
            "--quiet",
        ],
        check=False,
    )


def _configure_docker_auth(region: str) -> None:
    host = f"{region}-docker.pkg.dev"
    run(["gcloud", "auth", "configure-docker", host, "--quiet"], check=False)


def _build_and_push(project: str, region: str, repo: str, image_name: str, tag: str, cwd: str) -> str:
    image_uri = f"{region}-docker.pkg.dev/{project}/{repo}/{image_name}:{tag}"
    console.print(f"[cyan]Building & pushing[/cyan] {image_uri}")
    run(["gcloud", "builds", "submit", "--tag", image_uri, "--project", project], cwd=cwd, check=True)
    return image_uri


def _deploy_service(project: str, region: str, service: str, image_uri: str, token: str) -> str:
    console.print(f"[cyan]Deploying Cloud Run service[/cyan] {service} ({region})")
    run(
        [
            "gcloud",
            "run",
            "deploy",
            service,
            "--image",
            image_uri,
            "--region",
            region,
            "--project",
            project,
            "--allow-unauthenticated",
            "--set-env-vars",
            f"COLLABX_TOKEN={token}",
            "--quiet",
        ],
        check=True,
    )
    r = run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            service,
            "--region",
            region,
            "--project",
            project,
            "--format",
            "value(status.url)",
        ],
        check=True,
    )
    url = (r.out or "").strip()
    if not url:
        raise RuntimeError("Cloud Run service deployed but URL was empty. Try: gcloud run services list")
    return url.rstrip("/")


def gcp_up(
    *,
    repo_root: str,
    region: str = "us-central1",
    project: Optional[str] = None,
    service: Optional[str] = None,
    repo: str = "collabx",
    image_name: str = "collector",
    token: Optional[str] = None,
) -> Tuple[str, str, Dict]:
    project_id = _get_project(project)
    _ensure_services(project_id)
    _ensure_repo(project_id, region, repo)
    _configure_docker_auth(region)

    if not token:
        token = secrets.token_hex(32)
    if not service:
        service = f"collabx-{secrets.token_hex(4)}"
    tag = f"poc-{int(time.time())}"

    image_uri = _build_and_push(project_id, region, repo, image_name, tag, cwd=repo_root)
    url = _deploy_service(project_id, region, service, image_uri, token)

    resources = {
        "project": project_id,
        "region": region,
        "service": service,
        "repo": repo,
        "image_uri": image_uri,
    }
    return url, token, resources


def gcp_status(resources: Dict) -> Dict:
    project = resources.get("project")
    region = resources.get("region")
    service = resources.get("service")
    if not all([project, region, service]):
        raise RuntimeError("Missing GCP resource identifiers in state.")
    r = run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            service,
            "--region",
            region,
            "--project",
            project,
            "--format",
            "json(status.url,status.conditions)",
        ],
        check=True,
    )
    return {"raw": r.out}


def gcp_down(resources: Dict, delete_image: bool = True) -> None:
    project = resources.get("project")
    region = resources.get("region")
    service = resources.get("service")
    image_uri = resources.get("image_uri")

    if project and region and service:
        console.print(f"[cyan]Deleting Cloud Run service[/cyan] {service}")
        run(
            [
                "gcloud",
                "run",
                "services",
                "delete",
                service,
                "--region",
                region,
                "--project",
                project,
                "--quiet",
            ],
            check=False,
        )
    if delete_image and project and image_uri:
        console.print(f"[cyan]Deleting image[/cyan] {image_uri}")
        run(
            [
                "gcloud",
                "artifacts",
                "docker",
                "images",
                "delete",
                image_uri,
                "--delete-tags",
                "--quiet",
            ],
            check=False,
        )
