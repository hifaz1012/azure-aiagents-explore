#   This script demonstrates how to use the completeness evaluator in PromptFlow to evaluate the completeness of a response.
import os
from promptflow.core import AzureOpenAIModelConfiguration
from promptflow.client import load_flow
from datetime import datetime
from promptflow.evals.evaluate import evaluate
from dotenv import load_dotenv

load_dotenv(".env")


# Initialize Azure OpenAI Connection with your environment variables
model_config = AzureOpenAIModelConfiguration(
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
)

# load completeness evaluator from prompty file using promptflow
completeness_eval = load_flow(source="./completeness_evaluator.prompty", model={"configuration": model_config})

result = completeness_eval(context="Patient: I have a headache. Doctor: Take 2 tablets of panadol", answer="Doctor said Take 2 tablets of Ibuprofen daily")
print("Completeness Evaluation: ", result)

print("\n")

result = completeness_eval(context="Patient: I have a headache. Doctor: Take 2 tablets of Asprin and 1 tablet of IbuProfen", answer="Doctor said Take 2 tablets of Aspirin and 1 tablet of IbuProfen")
print("Completeness Evaluation: ", result)

