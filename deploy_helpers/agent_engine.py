from vertexai.agent_engines import AdkApp
import vertexai

class AgentEngineClient:
    """A client to interact with the Vertex AI Agent Engines API."""

    def __init__(self, project_id: str, location: str):
        self.client = vertexai.Client(project=project_id, location=location)

    def list_deployments(self):
        return self.client.agent_engines.list()

    def get_deployment(self, name: str):
        return self.client.agent_engines.get(name=name)

    def get_deployment_by_display_name(self, name: str):
        """Searches for a deployment by its display name."""
        try:
            deployments = self.list_deployments()
            for deployment in deployments:
                if deployment.api_resource.display_name == name:
                    return deployment
        except Exception as e:
            print(f"Warning: Could not list existing deployments. Error: {e}")
        return None

    def delete_deployment(self, name: str, force: bool = True):
        deployment = self.get_deployment(name)
        deployment.delete(force=force)

    def update_deployment(self, name: str, agent: AdkApp, config: dict):
        return self.client.agent_engines.update(
            name=name,
            agent=agent,
            config=config,
        )

    def create_deployment(self, agent: AdkApp, config: dict):
        return self.client.agent_engines.create(
            agent=agent,
            config=config,
        )

    def get_session(self, resource_name: str, user_id: str, session_id: str):
        remote_app = self.get_deployment(name=resource_name)
        return remote_app.get_session(user_id=user_id, session_id=session_id)

    def list_sessions(self, resource_name: str, user_id: str):
        remote_app = self.get_deployment(name=resource_name)
        return remote_app.list_sessions(user_id=user_id)

    def stream_query(self, resource_name: str, user_id: str, session_id: str, message: str):
        remote_app = self.get_deployment(name=resource_name)
        return remote_app.async_stream_query(
            user_id=user_id,
            session_id=session_id,
            message=message,
        )
