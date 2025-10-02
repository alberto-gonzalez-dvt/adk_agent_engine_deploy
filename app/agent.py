from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.tools.bigquery import BigQueryCredentialsConfig, BigQueryToolset
import google.auth
import dotenv

from google import genai

from .prompts import COMPRAS_AGENT_PROMPT, CALIDAD_AGENT_PROMPT, PEDIDOS_AGENT_PROMPT

dotenv.load_dotenv()

credentials, _ = google.auth.default()
credentials_config = BigQueryCredentialsConfig(credentials=credentials)
bigquery_toolset = BigQueryToolset(
  credentials_config=credentials_config
)

genai_client = genai.Client(vertexai=True, project='ocr-digitalizacion-425708', location='europe-west1')

def query_gcs_document(gcs_file_path: str, question: str) -> str:
    """
    Reads a document directly from a Google Cloud Storage (GCS) URI and answers a question about its content.

    Args:
        gcs_file_path (str): The full GCS path to the file, e.g., 'gs://my-bucket/documents/report.pdf'.
        question (str): The specific question to ask about the document's content.

    Returns:
        str: The answer to the question based on the document's content, or an error message if the file cannot be accessed.
    """
    

    try:
        file_part = genai.types.Part.from_uri(file_uri=gcs_file_path, mime_type='application/pdf')

        response = genai_client.models.generate_content( 
            model='gemini-2.5-flash',
            contents=[str(question), file_part],
        )

        return response.text

    except Exception as e:
        print(f"An error occurred: {e}")
        return f"Error: Failed to access or process the file at {gcs_file_path}."

calidad_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="calidad_agent",
    description="Agent that answers question about quality documents by executing SQL queries.",
    instruction=CALIDAD_AGENT_PROMPT,
    tools=[bigquery_toolset, query_gcs_document]
)

compras_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="compras_agent",
    description="Agent that answers question about buys by executing SQL queries.",
    instruction=COMPRAS_AGENT_PROMPT,
    tools=[bigquery_toolset, query_gcs_document]
)

pedidos_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="pedidos_agent",
    description="Agent that answers question about orders by executing SQL queries.",
    instruction=PEDIDOS_AGENT_PROMPT,
    tools=[bigquery_toolset, query_gcs_document]
)



root_agent = Agent(
 model="gemini-2.5-flash",
 name="bigquery_agent",
 description="Agent that answers questions about BigQuery data by executing SQL queries.",
 instruction=(
    """
    You are an orchestration agent.
    You can delegate questions about quality documents to the calidad_agent.
    You can delegate question about buys to the compras_agent.
    You can delegate question about orders to the pedidos_agent.

    You work for Alifarma, a pharmaceutical company.
    """
 ),
 sub_agents=[calidad_agent, compras_agent, pedidos_agent],
)

def get_bigquery_agent():
 return root_agent