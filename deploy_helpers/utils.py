import json
import os
import tomllib
import questionary
import typer

ENGINE_FILE = "engine.json"

def load_engine_data() -> dict:
    """Loads the entire engine.json file."""
    if not os.path.exists(ENGINE_FILE):
        return {"deployments": {}}
    try:
        with open(ENGINE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"deployments": {}}

def save_engine_data(data: dict):
    """Saves the entire data structure to engine.json."""
    with open(ENGINE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_deployment_config(name: str) -> dict | None:
    """Returns the config for a specific deployment."""
    return load_engine_data().get("deployments", {}).get(name)

def select_deployment_interactively() -> str | None:
    """Presents an interactive list of saved deployments for the user to choose from."""
    data = load_engine_data()
    deployments = data.get("deployments", {})
    if not deployments:
        typer.echo(typer.style("No saved deployments found in engine.json.", fg=typer.colors.YELLOW))
        return None

    choices = list(deployments.keys())
    if not choices:
        typer.echo(typer.style("No deployments available to select.", fg=typer.colors.YELLOW))
        return None

    deployment_name = questionary.select(
        "Please choose a deployment:",
        choices=choices,
    ).ask()

    return deployment_name

def verify_dependencies(prod_reqs: list[str]) -> bool:
    """Compares production requirements with pyproject.toml and asks for confirmation on mismatch."""
    try:
        with open("pyproject.toml", "rb") as f:
            toml_data = tomllib.load(f)
        toml_deps = {dep.split("==")[0].split("[")[0]: dep.split("==")[1] 
                     for dep in toml_data.get("project", {}).get("dependencies", []) if "==" in dep}
    except (FileNotFoundError, tomllib.TOMLDecodeError) as e:
        print(f"Warning: Could not read or parse pyproject.toml for verification. Skipping check. Error: {e}")
        return True

    mismatches = []
    for req in prod_reqs:
        req_name, req_version = req.split("==")
        req_name = req_name.split("[")[0]

        if req_name in toml_deps and toml_deps[req_name] != req_version:
            mismatches.append(
                f"- {req_name}: Script wants {req_version}, but pyproject.toml has {toml_deps[req_name]}"
            )

    if not mismatches:
        return True

    typer.echo(typer.style("\n--- DEPENDENCY MISMATCH WARNING ---", fg=typer.colors.YELLOW))
    typer.echo("The following dependencies in your deployment script do not match pyproject.toml:")
    for mismatch in mismatches:
        typer.echo(typer.style(mismatch, fg=typer.colors.YELLOW))
    typer.echo("This can lead to unexpected behavior between local and production environments.")
    
    return questionary.confirm("Do you want to proceed with the deployment anyway?").ask()
