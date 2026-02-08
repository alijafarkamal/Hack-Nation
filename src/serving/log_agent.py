"""Log the Ghana Medical Agent to MLflow and register in Unity Catalog.

Run this script from the project root:
    python -m src.serving.log_agent

Or from a Databricks notebook:
    %run ./src/serving/log_agent

This will:
  1. Log the ResponsesAgent wrapper as an MLflow pyfunc model
  2. Register it in Unity Catalog (if configured)
  3. Print the model URI for deployment

Ref: https://docs.databricks.com/aws/en/generative-ai/agent-framework/log-agent
Ref: https://docs.databricks.com/aws/en/generative-ai/agent-framework/deploy-agent
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import mlflow

# ── Configuration ──────────────────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).parent / "model_config.yaml"

# Unity Catalog model name (override via env var for different environments)
UC_MODEL_NAME = os.getenv(
    "UC_MODEL_NAME", "hack_nation.ghana_medical.medical_intelligence_agent"
)


def log_agent() -> str:
    """Log the agent to MLflow and return the model URI.

    Returns:
        The MLflow model URI (e.g., 'runs:/<run_id>/agent').
    """
    model_config = mlflow.models.ModelConfig(
        development_config=str(_CONFIG_PATH)
    )

    with mlflow.start_run(run_name="ghana-medical-agent") as run:
        # Log the ResponsesAgent wrapper
        model_info = mlflow.pyfunc.log_model(
            python_model=str(
                Path(__file__).parent / "agent_wrapper.py"
            ),
            artifact_path="agent",
            model_config=str(_CONFIG_PATH),
            pip_requirements=[
                "mlflow>=3.1.3",
                "databricks-sdk",
                "databricks-vectorsearch",
                "databricks-agents>=1.2.0",
                "langgraph>=0.2",
                "python-dotenv",
                "requests",
            ],
            # Include the full src/ package as code dependencies
            code_paths=[
                str(Path(__file__).resolve().parent.parent),  # src/
            ],
        )

        # Tag the run for easy identification
        mlflow.set_tags(
            {
                "agent_type": "langgraph_multi_agent",
                "challenge": "hack_nation_medical_deserts",
                "framework": "mosaic_ai_agent_framework",
            }
        )

        model_uri = f"runs:/{run.info.run_id}/agent"
        print(f"\n{'='*60}")
        print(f"Agent logged successfully!")
        print(f"  Run ID:    {run.info.run_id}")
        print(f"  Model URI: {model_uri}")
        print(f"{'='*60}\n")

        return model_uri


def register_model(model_uri: str) -> None:
    """Register the logged model in Unity Catalog.

    Args:
        model_uri: MLflow model URI from log_agent().
    """
    try:
        result = mlflow.register_model(model_uri, UC_MODEL_NAME)
        print(f"Registered as: {UC_MODEL_NAME} v{result.version}")
    except Exception as e:
        print(f"Unity Catalog registration skipped: {e}")
        print("(This is normal if running outside Databricks)")


def deploy_agent(model_uri: str) -> None:
    """Deploy the agent to a Databricks Model Serving endpoint.

    Requires `databricks-agents` and a Databricks workspace.

    Args:
        model_uri: MLflow model URI from log_agent().
    """
    try:
        from databricks import agents

        agents.deploy(
            UC_MODEL_NAME,
            model_uri,
            environment_vars={
                "DATABRICKS_HOST": "{{secrets/ghana-medical/databricks-host}}",
                "DATABRICKS_TOKEN": "{{secrets/ghana-medical/databricks-token}}",
                "GENIE_SPACE_ID": "{{secrets/ghana-medical/genie-space-id}}",
                "VECTOR_SEARCH_INDEX": "{{secrets/ghana-medical/vs-index}}",
                "VECTOR_SEARCH_ENDPOINT": "{{secrets/ghana-medical/vs-endpoint}}",
                "OPENROUTER_API_KEY": "{{secrets/ghana-medical/openrouter-key}}",
            },
            scale_to_zero=True,
        )
        print(f"Deployment initiated for {UC_MODEL_NAME}")
        print("Monitor at: Model Serving > Endpoints in your Databricks workspace")
    except ImportError:
        print("databricks-agents not installed. Install with: pip install databricks-agents")
    except Exception as e:
        print(f"Deployment failed: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Log and deploy the Ghana Medical Agent")
    parser.add_argument("--register", action="store_true", help="Register in Unity Catalog")
    parser.add_argument("--deploy", action="store_true", help="Deploy to Model Serving")
    args = parser.parse_args()

    uri = log_agent()

    if args.register:
        register_model(uri)

    if args.deploy:
        deploy_agent(uri)
