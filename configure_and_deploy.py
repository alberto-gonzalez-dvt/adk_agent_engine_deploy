import json
import argparse
import asyncio
import os
from vertexai.agent_engines import AdkApp
import vertexai

from app.agent import root_agent

from google.adk.sessions import VertexAiSessionService

GCP_PROJECT="alberto-gonzalez-sandbox"
#GCP_PROJECT="667925560760"
GCP_REGION= "europe-west1" #"us-central1"
STAGING_BUCKET = "gs://2025_09_alifarma_agente_datos"
ENGINE_FILE = "engine.json"

client = vertexai.Client(project=GCP_PROJECT, location=GCP_REGION)
vertexai.init(
    project=GCP_PROJECT,
    location=GCP_REGION,
    staging_bucket=STAGING_BUCKET,
)

def save_engine(data: dict):
    with open(ENGINE_FILE, "w") as f:
        json.dump(data, f)

def load_engine() -> dict:
    try:
        with open(ENGINE_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    return data

def deploy(name: str):
    app = AdkApp(
            agent=root_agent,
            enable_tracing=True,
        )

    # Search for existing deployment
    existing_deployment = None
    print(f"Searching for existing deployments named '{name}'...")
    try:
        deployments = client.agent_engines.list()
        for deployment in deployments:
            if deployment.api_resource.display_name == name:
                existing_deployment = deployment
                break
    except Exception as e:
        print(f"Warning: Could not list existing deployments. Will attempt to create a new one. Error: {e}")

    resource_name = None
    if existing_deployment:
        print(f"Found existing deployment: {existing_deployment.api_resource.name}. Attempting to update.")
        try:
            remote_app = client.agent_engines.update(
                name=existing_deployment.api_resource.name,
                agent=app,
                config={
                    "displayName": name,
                    "staging_bucket": STAGING_BUCKET,
                    "requirements" : [
                        "google-cloud-aiplatform[agent_engines,adk]==1.117.0",
                        "cloudpickle==3.1.1",
                        "pydantic==2.11.9",
                        "google-adk==1.15.1",
                    ],
                    "extra_packages": ["./app"],
                },
            )
            print(f"Successfully updated deployment: {remote_app.api_resource.name}")
            resource_name = remote_app.api_resource.name
        except Exception as e:
            print(f"ERROR: Failed to update deployment: {e}")
            return # Stop if update fails

    else:
        print(f"No existing agent found with name '{name}'. Creating a new one.")
        try:
            remote_app = client.agent_engines.create(
                agent=app,
                config={
                    "displayName": name,
                    "staging_bucket": STAGING_BUCKET,
                    "requirements" : [
                        "google-cloud-aiplatform[agent_engines,adk]==1.117.0",
                        "cloudpickle==3.1.1",
                        "pydantic==2.11.9",
                        "google-adk==1.15.1",
                    ],
                    "extra_packages": ["./app"],
                },
            )
            print(f"Created remote app: {remote_app.api_resource.name}")
            resource_name = remote_app.api_resource.name
        except Exception as e:
            print(f"ERROR: Failed to create deployment: {e}")
            return # Stop if create fails

    if resource_name:
        save_engine({"resource_name": resource_name, "agent_name": name})
        print(f"Resource name and agent name saved to {ENGINE_FILE}")

def hello():
    print("Hello, Alifarma!")

async def create_session(resource_name: str = None, user_id: str = None):
    engine_data = load_engine()
    if resource_name is None:
        resource_name = engine_data.get("resource_name")
        if not resource_name:
            raise ValueError("No resource_name found. Deploy the agent first.")
    if user_id is None:
        raise ValueError("user_id must be provided.")


    session_service = VertexAiSessionService(project=GCP_PROJECT, location=GCP_REGION)

    session_service = await session_service.create_session(app_name=resource_name, user_id=user_id)

    session_id = session_service.id

    engine_data["user_id"] = user_id
    engine_data["session_id"] = session_id
    engine_data["resource_name"] = resource_name
    save_engine(engine_data)

    print(f"--- Examining Session Properties ---")
    print(f"ID (`id`):                {session_service.id}")
    print(f"Application Name (`app_name`): {session_service.app_name}")
    print(f"User ID (`user_id`):         {session_service.user_id}")
    print(f"State (`state`):           {session_service.state}") # Note: Only shows initial state here
    print(f"Events (`events`):         {session_service.events}") # Initially empty
    print(f"Last Update (`last_update_time`): {session_service.last_update_time:.2f}")
    print(f"---------------------------------")

def get_session(resource_name: str = None, user_id: str = None, session_id: str = None) -> None:
    """Gets a specific session."""
    engine_data = load_engine()
    if resource_name is None:
        resource_name = engine_data.get("resource_name")
        if not resource_name:
            raise ValueError("No resource_name found. Deploy the agent first.")
    
    if user_id is None:
        user_id = engine_data.get("user_id")
        if user_id is None:
            raise ValueError("user_id must be provided.")

    if session_id is None:
        session_id = engine_data.get("session_id")
        if session_id is None:
            raise ValueError("session_id must be provided.")

    remote_app = client.agent_engines.get(name=resource_name)
    session = remote_app.get_session(user_id=user_id, session_id=session_id)
    print("Session details:")
    print(f"  ID: {session['id']}")
    print(f"  User ID: {session['user_id']}")
    print(f"  App name: {session['app_name']}")
    print(f"  Last update time: {session['last_update_time']}")

def list_deployments() -> None:
    """Lists all deployments."""
    deployments = client.agent_engines.list()
    if not deployments:
        print("No deployments found.")
        return
    print("Deployments:")
    for deployment in deployments:
        print(f"- {deployment.api_resource.name}")

def list_sessions(resource_name: str = None, user_id: str = None) -> None:
    """Lists all sessions for the specified user."""
    engine_data = load_engine()
    if resource_name is None:
        resource_name = engine_data.get("resource_name")
        if not resource_name:
            raise ValueError("No resource_name found. Deploy the agent first.")
    if user_id is None:
        user_id = engine_data.get("user_id")
        if user_id is None:
            raise ValueError("user_id must be provided.")

    remote_app = client.agent_engines.get(name=resource_name)
    sessions = remote_app.list_sessions(user_id=user_id)
    print(f"Sessions for user '{user_id}':")
    if not sessions:
        print("No sessions found.")
        return
    for session in sessions:
        print(f"- Session ID: {session['id']}")

def delete_deployment(resource_name: str = None) -> None:
    """Deletes an existing deployment."""
    engine_data = load_engine()
    if resource_name is None:
        resource_name = engine_data.get("resource_name")
        if not resource_name:
            raise ValueError("No resource_name found to delete. Provide one or deploy first.")
    
    remote_app = client.agent_engines.get(name=resource_name)
    remote_app.delete(force=True)
    print(f"Deleted remote app: {resource_name}")
    if os.path.exists(ENGINE_FILE):
        os.remove(ENGINE_FILE)
        print(f"Deleted {ENGINE_FILE}")


async def send_message(resource_name: str = None, user_id: str = None, session_id: str = None, message: str = None) -> list:
    """Sends a message to the deployed agent (asynchronous) and returns a list of events."""
    engine_data = load_engine()
    
    if resource_name is None:
        resource_name = engine_data.get("resource_name")
        if not resource_name:
            raise ValueError("No resource_name found. Deploy the agent first.")
    
    if user_id is None:
        user_id = engine_data.get("user_id")
        if user_id is None:
            raise ValueError("user_id must be provided.")

    if session_id is None:
        session_id = engine_data.get("session_id")
        if session_id is None:
            raise ValueError("session_id must be provided.")
            
    if not message:
        raise ValueError("message must be provided.")

    try:
        remote_app = client.agent_engines.get(name=resource_name)
    except Exception as e:
        raise RuntimeError(f"Error getting agent engine '{resource_name}': {e}")

    events_list = []
    print(f"Sending message to session {session_id}:")
    print(f"Message: {message}\n")
    print("=" * 80)
    print("Response:\n")


        
    try:
        async for event in remote_app.async_stream_query(
            user_id=user_id,
            session_id=session_id,
            message=message,
        ):
            events_list.append(event)
            print(f"Event: {event}")
            
 
    except Exception as e:
        raise RuntimeError(f"Error sending message to session '{session_id}': {e}")

    print(f"\n\n{'=' * 80}")
    print(f"Total events received: {len(events_list)}")
    
    # Mostrar un resumen de los eventos si hay alguno
    if events_list:
        print("\nEvent types received:")
        event_types = {}
        for event in events_list:
            event_type = type(event).__name__
            event_types[event_type] = event_types.get(event_type, 0) + 1
        for event_type, count in event_types.items():
            print(f"  - {event_type}: {count}")
    
    return events_list

def diagnose_agent(resource_name: str = None):
    """Diagnoses the agent deployment and configuration."""
    engine_data = load_engine()
    
    if resource_name is None:
        resource_name = engine_data.get("resource_name")
        if not resource_name:
            raise ValueError("No resource_name found. Deploy the agent first.")
    
    print("=" * 80)
    print("AGENT DIAGNOSIS")
    print("=" * 80)
    
    try:
        print("\n1. Fetching agent information...")
        remote_app = client.agent_engines.get(name=resource_name)
        print(f"   ✓ Agent found: {resource_name}")
        
        print("\n2. Agent API Resource details:")
        api_resource = remote_app.api_resource
        print(f"   Name: {api_resource.name}")
        print(f"   Display Name: {api_resource.display_name}")
        print(f"   Create Time: {api_resource.create_time}")
        print(f"   Update Time: {api_resource.update_time}")
        
        print("\n3. Remote App attributes:")
        if hasattr(remote_app, '__dict__'):
            for key, value in remote_app.__dict__.items():
                print(f"   {key}: {value}")
        
        print("\n4. Available methods:")
        if hasattr(remote_app.api_resource, 'spec') and hasattr(remote_app.api_resource.spec, 'class_methods'):
            for method in remote_app.api_resource.spec.class_methods:
                print(f"   - {method.get('name', 'unknown')}: {method.get('api_mode', 'unknown')} mode")
        
        print("\n5. Testing async_stream_query method...")
        print("   NOTE: This requires running in async context. Use send_message command instead.")
        print("   If send_message returns 0 events, the issue is likely in the agent definition.")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n✗ Diagnosis failed: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)

async def main():
    '''Main function to parse arguments and execute commands.'''
    parser = argparse.ArgumentParser(description="Deploy and manage Alifarma agent.")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # Comando 'deploy'
    parser_deploy = subparsers.add_parser("deploy", help="Deploys the agent to Vertex AI Agent Engines.")
    parser_deploy.add_argument("name", type=str, help="The name for the new agent engine.")

    # Comando 'hello'
    subparsers.add_parser("hello", help="Prints a hello message.")

    # Comando 'create_session'
    parser_create_session = subparsers.add_parser("create_session", help="Creates a new session for a deployed agent.")
    parser_create_session.add_argument("--resource-name", type=str, default=None, help="Resource name of the deployed agent. If omitted, uses the last deployed engine.")
    parser_create_session.add_argument("--user-id", type=str, help="The user ID for the new session.")

    # Comando 'list_deployments'
    subparsers.add_parser("list_deployments", help="Lists all deployments.")

    # Comando 'get_session'
    parser_get_session = subparsers.add_parser("get_session", help="Gets a specific session.")
    parser_get_session.add_argument("--resource-name", type=str, default=None, help="Resource name of the deployed agent. If omitted, uses the last deployed engine.")
    parser_get_session.add_argument("--user-id", type=str, help="The user ID for the session.")
    parser_get_session.add_argument("--session-id", type=str, help="The session ID to get.")

    # Comando 'list_sessions'
    parser_list_sessions = subparsers.add_parser("list_sessions", help="Lists all sessions for a user.")
    parser_list_sessions.add_argument("--resource-name", type=str, default=None, help="Resource name of the deployed agent. If omitted, uses the last deployed engine.")
    parser_list_sessions.add_argument("--user-id", type=str, help="The user ID to list sessions for.")

    # Comando 'delete_deployment'
    parser_delete_deployment = subparsers.add_parser("delete_deployment", help="Deletes an existing deployment.")
    parser_delete_deployment.add_argument("--resource-name", type=str, default=None, help="Resource name of the deployed agent to delete. If omitted, uses the last deployed engine.")

    # Comando 'send_message'
    parser_send_message = subparsers.add_parser("send_message", help="Sends a message to a session.")
    parser_send_message.add_argument("message", type=str, help="The message to send.")
    parser_send_message.add_argument("--resource-name", type=str, default=None, help="Resource name of the deployed agent. If omitted, uses the last deployed engine.")
    parser_send_message.add_argument("--user-id", type=str, help="The user ID for the session.")
    parser_send_message.add_argument("--session-id", type=str, help="The session ID to send the message to.")

    # Comando 'diagnose'
    parser_diagnose = subparsers.add_parser("diagnose", help="Diagnoses the agent deployment.")
    parser_diagnose.add_argument("--resource-name", type=str, default=None, help="Resource name of the deployed agent.")


    args = parser.parse_args()

    if args.command == "deploy":
        deploy(args.name)
    elif args.command == "hello":
        hello()
    elif args.command == "create_session":
        await create_session(resource_name=args.resource_name, user_id=args.user_id)
    elif args.command == "list_deployments":
        list_deployments()
    elif args.command == "get_session":
        get_session(resource_name=args.resource_name, user_id=args.user_id, session_id=args.session_id)
    elif args.command == "list_sessions":
        list_sessions(resource_name=args.resource_name, user_id=args.user_id)
    elif args.command == "delete_deployment":
        delete_deployment(resource_name=args.resource_name)
    elif args.command == "send_message":
        await send_message(resource_name=args.resource_name, user_id=args.user_id, session_id=args.session_id, message=args.message)
    elif args.command == "diagnose":
        diagnose_agent(resource_name=args.resource_name)

if __name__ == "__main__":
    asyncio.run(main())