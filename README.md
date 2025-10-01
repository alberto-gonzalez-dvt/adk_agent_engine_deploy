# adk_agent_engine_deploy

## Cómo ejecutar

1.  **Crea el entorno virtual:**
    ```bash
    uv venv
    ```

2.  **Sincroniza las dependencias:**
    ```bash
    uv sync
    ```

3.  **Activa el entorno virtual:**
    ```bash
    .venv\Scripts\activate
    ```

## Desplegar en Agent Engine

Para desplegar el ADK en Agent Engine, puedes usar el siguiente comando. Asegúrate de reemplazar `demo` con el nombre de tu proyecto:

```bash
python .\configure_and_deploy.py deploy demo
```

## Documentación

### Despliegue Agent Engine
- [Reasoning Engine REST API](https://cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/projects.locations.reasoningEngines#ReasoningEngine)
- [ADK Agent Engine Deployment](https://google.github.io/adk-docs/deploy/agent-engine/)
- [Troubleshooting Agent Engine](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/troubleshooting/use)
- [Agent Engine Migration](https://cloud.google.com/vertex-ai/generative-ai/docs/deprecations/agent-engine-migration#after_2)

### Session
- [ADK Session](https://google.github.io/adk-docs/sessions/session/)