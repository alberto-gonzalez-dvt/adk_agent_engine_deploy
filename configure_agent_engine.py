import asyncio
import os
import typer
from typing_extensions import Annotated
import vertexai
from dotenv import load_dotenv

# Load environment variables from .env file at the very beginning
load_dotenv()

from app.agent import root_agent
from google.adk.sessions import VertexAiSessionService
from deploy_helpers.utils import (
    load_engine_data,
    save_engine_data,
    get_deployment_config,
    select_deployment_interactively,
    verify_dependencies,
)
from deploy_helpers.agent_engine import AgentEngineClient

# Create the Typer App and sub-apps for namespacing
app = typer.Typer(add_completion=False, help="A CLI for deploying and managing Alifarma agent engines.")
deployments_app = typer.Typer(help="Manage saved deployments.")
sessions_app = typer.Typer(help="Manage user sessions.")
app.add_typer(deployments_app, name="deployments")
app.add_typer(sessions_app, name="sessions")

# --- Global Config & Initializations ---
GCP_PROJECT = os.environ.get("GCP_PROJECT")
GCP_REGION = os.environ.get("GCP_REGION")
STAGING_BUCKET = os.environ.get("STAGING_BUCKET")

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """A CLI for deploying and managing Alifarma agent engines."""
    if ctx.invoked_subcommand is None:
        typer.echo("Welcome to the Alifarma Agent Engine Manager!")
        typer.echo("This is an interactive CLI. Please provide a command to run.")
        typer.echo("Example: python configure_agent_engine.py deployments list")
        # Display help text
        raise typer.Exit(ctx.get_help())

    if not all([GCP_PROJECT, GCP_REGION, STAGING_BUCKET]):
        raise typer.Exit("Error: GCP_PROJECT, GCP_REGION, and STAGING_BUCKET must be set.")
    vertexai.init(project=GCP_PROJECT, location=GCP_REGION, staging_bucket=STAGING_BUCKET)

# --- Top-level Commands ---

@app.command()
def deploy(name: Annotated[str, typer.Argument(help="The name for the new or existing agent engine.")] = None):
    """Deploys or updates an agent engine."""
    if not name:
        name = typer.prompt("Please enter a name for the deployment")

    engine_client = AgentEngineClient(project_id=GCP_PROJECT, location=GCP_REGION)
    prod_requirements = [
        "google-cloud-aiplatform[agent_engines,adk]==1.117.0",
        "cloudpickle==3.1.1",
        "pydantic==2.11.9",
        "google-adk==1.15.1",
        "questionary==2.0.1",
        "typer[all]",
    ]
    if not verify_dependencies(prod_requirements):
        raise typer.Abort()

    from vertexai.agent_engines import AdkApp
    app_instance = AdkApp(agent=root_agent, enable_tracing=True, enable_websockets=True)
    common_config = {"requirements": prod_requirements, "extra_packages": ["./app"]}

    typer.echo(f"Searching for existing deployments named '{name}'...")
    existing_deployment = engine_client.get_deployment_by_display_name(name)

    resource_name = None
    if existing_deployment:
        typer.echo(f"Found existing deployment: {existing_deployment.api_resource.name}.")
        if not typer.confirm(f"Do you want to overwrite it?"):
            raise typer.Abort()
        typer.echo("Attempting to update...")
        try:
            update_config = {**common_config, "displayName": name}
            remote_app = engine_client.update_deployment(name=existing_deployment.api_resource.name, agent=app_instance, config=update_config)
            resource_name = remote_app.api_resource.name
            typer.echo(typer.style(f"Successfully updated deployment: {resource_name}", fg=typer.colors.GREEN))
        except Exception as e:
            typer.echo(typer.style(f"ERROR: Failed to update deployment: {e}", fg=typer.colors.RED)); raise typer.Exit(1)
    else:
        typer.echo(f"No existing agent found with name '{name}'. Creating a new one...")
        try:
            create_config = {**common_config, "displayName": name, "staging_bucket": STAGING_BUCKET}
            remote_app = engine_client.create_deployment(agent=app_instance, config=create_config)
            resource_name = remote_app.api_resource.name
            typer.echo(typer.style(f"Successfully created deployment: {resource_name}", fg=typer.colors.GREEN))
        except Exception as e:
            typer.echo(typer.style(f"ERROR: Failed to create deployment: {e}", fg=typer.colors.RED)); raise typer.Exit(1)

    if resource_name:
        typer.echo("Saving deployment info to engine.json...")
        data = load_engine_data()
        if "deployments" not in data: data["deployments"] = {}
        data["deployments"][name] = {"resource_name": resource_name}
        save_engine_data(data)
        typer.echo("Done.")

@app.command()
def send_message(message: Annotated[str, typer.Argument(help="The message to send.")]):
    """Sends a message to a session of a chosen deployment."""
    async def _send_message():
        chosen_name = select_deployment_interactively()
        if not chosen_name: raise typer.Abort()
        config = get_deployment_config(chosen_name)

        last_session = config.get("last_session", {})
        user_id = last_session.get("user_id") or typer.prompt("Please enter a user ID")
        session_id = last_session.get("session_id")

        if not session_id:
            typer.echo(typer.style("No active session found for this deployment. Please create one first.", fg=typer.colors.YELLOW))
            raise typer.Abort()

        engine_client = AgentEngineClient(project_id=GCP_PROJECT, location=GCP_REGION)
        params = {"resource_name": config["resource_name"], "user_id": user_id, "session_id": session_id, "message": message}
        
        typer.echo(f"Sending message to session {session_id}:\nMessage: {message}\n")
        typer.echo("=" * 80)
        typer.echo("Response:\n")
        try:
            async for event in engine_client.stream_query(**params):
                typer.echo(f"Event: {event}")
        except Exception as e:
            raise RuntimeError(f"Error sending message: {e}")

    asyncio.run(_send_message())

@app.command()
def diagnose():
    """Gets and displays detailed diagnostic information for a deployment."""
    chosen_name = select_deployment_interactively()
    if not chosen_name: raise typer.Abort()
    config = get_deployment_config(chosen_name)
    resource_name = config["resource_name"]

    typer.echo("=" * 80)
    typer.echo(f"AGENT DIAGNOSIS for '{chosen_name}'")
    typer.echo("=" * 80)
    
    try:
        engine_client = AgentEngineClient(project_id=GCP_PROJECT, location=GCP_REGION)
        typer.echo("\n1. Fetching agent information...")
        remote_app = engine_client.get_deployment(name=resource_name)
        typer.echo(f"   ✓ Agent found: {resource_name}")
        
        api_resource = remote_app.api_resource
        typer.echo(f"\n2. Agent API Resource details:\n   Name: {api_resource.name}\n   Display Name: {api_resource.display_name}\n   Create Time: {api_resource.create_time}\n   Update Time: {api_resource.update_time}")
        
        typer.echo("\n3. Remote App attributes:")
        for key, value in remote_app.__dict__.items(): typer.echo(f"   {key}: {value}")
        
    except Exception as e:
        typer.echo(typer.style(f"\n✗ Diagnosis failed: {e}", fg=typer.colors.RED))
        import traceback; traceback.print_exc()

# --- Deployment Commands ---

@deployments_app.command("list")
def list_saved_deployments():
    """Lists all saved deployments in engine.json."""
    data = load_engine_data()
    deployments = data.get("deployments", {})
    if not deployments:
        typer.echo("No saved deployments found."); return
    typer.echo("Saved deployments:")
    for name, config in deployments.items():
        typer.echo(f"- {name} ({config.get('resource_name')})")

@deployments_app.command("delete")
def delete_deployment():
    """Deletes a deployment from Google Cloud and from engine.json."""
    chosen_name = select_deployment_interactively()
    if not chosen_name: raise typer.Abort()
    config = get_deployment_config(chosen_name)

    if not typer.confirm(f"You are about to PERMANENTLY delete the deployment '{chosen_name}' from Google Cloud. Are you sure?"):
        raise typer.Abort()

    try:
        engine_client = AgentEngineClient(project_id=GCP_PROJECT, location=GCP_REGION)
        engine_client.delete_deployment(config["resource_name"])
        typer.echo(typer.style(f"Successfully deleted remote app: {config['resource_name']}", fg=typer.colors.GREEN))
        
        data = load_engine_data()
        if chosen_name in data.get("deployments", {}):
            del data["deployments"][chosen_name]
            save_engine_data(data)
            typer.echo(f"Removed '{chosen_name}' from engine.json.")
    except Exception as e:
        typer.echo(typer.style(f"ERROR: Failed to delete deployment: {e}", fg=typer.colors.RED)); raise typer.Exit(1)

# --- Session Commands ---

@sessions_app.command("create")
def create_session_command():
    """Creates a new session for a deployed agent."""
    async def _create_session():
        chosen_name = select_deployment_interactively()
        if not chosen_name: raise typer.Abort()
        config = get_deployment_config(chosen_name)

        user_id = typer.prompt("Please enter a user ID")

        session_service = VertexAiSessionService(project=GCP_PROJECT, location=GCP_REGION)
        new_session = await session_service.create_session(app_name=config["resource_name"], user_id=user_id)
        
        data = load_engine_data()
        if "last_session" not in data["deployments"][chosen_name]:
            data["deployments"][chosen_name]["last_session"] = {}
        data["deployments"][chosen_name]["last_session"] = {"user_id": new_session.user_id, "session_id": new_session.id}
        save_engine_data(data)

        typer.echo(typer.style(f"Session created for deployment '{chosen_name}'", fg=typer.colors.GREEN))
        typer.echo(f"  User ID: {new_session.user_id}\n  Session ID: {new_session.id}")
    asyncio.run(_create_session())

@sessions_app.command("list")
def list_sessions_command():
    """Lists all sessions for a given user of a deployment."""
    chosen_name = select_deployment_interactively()
    if not chosen_name: raise typer.Abort()
    config = get_deployment_config(chosen_name)

    user_id = typer.prompt("Please enter the user ID to list sessions for")

    engine_client = AgentEngineClient(project_id=GCP_PROJECT, location=GCP_REGION)
    sessions = engine_client.list_sessions(resource_name=config["resource_name"], user_id=user_id)
    
    typer.echo(f"Sessions for user '{user_id}' on deployment '{chosen_name}':")
    if not sessions:
        typer.echo("No sessions found."); return
    for session in sessions:
        typer.echo(f"- Session ID: {session['id']}")

if __name__ == "__main__":
    app()