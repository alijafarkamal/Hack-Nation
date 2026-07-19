"""Log care-india agent to MLflow; optional UC register and deploy."""

import os
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import mlflow  # noqa: E402

_CONFIG_PATH = Path(__file__).parent / "model_config.yaml"

UC_MODEL_NAME = os.getenv(
    "UC_MODEL_NAME", "hack_nation.india_medical.care_india_agent"
)


def log_agent() -> str:
    model_config = mlflow.models.ModelConfig(development_config=str(_CONFIG_PATH))
    with mlflow.start_run(run_name="care-india-agent") as run:
        _ = model_config
        model_info = mlflow.pyfunc.log_model(
            python_model=str(Path(__file__).parent / "agent_wrapper.py"),
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
            code_paths=[str(Path(__file__).resolve().parent.parent)],
        )
        _ = model_info
        mlflow.set_tags(
            {
                "agent_type": "langgraph_multi_agent",
                "product": "care-india",
            }
        )
        return f"runs:/{run.info.run_id}/agent"


def register_model(model_uri: str) -> None:
    try:
        result = mlflow.register_model(model_uri, UC_MODEL_NAME)
        print(f"Registered: {UC_MODEL_NAME} v{result.version}")
    except Exception as e:
        print(f"Registration skipped: {e}")


def deploy_agent(model_uri: str) -> None:
    try:
        from databricks import agents

        agents.deploy(
            UC_MODEL_NAME,
            model_uri,
            environment_vars={},
            scale_to_zero=True,
        )
    except Exception as e:
        print(f"Deploy skipped: {e}")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--register", action="store_true")
    p.add_argument("--deploy", action="store_true")
    args = p.parse_args()
    uri = log_agent()
    print(uri)
    if args.register:
        register_model(uri)
    if args.deploy:
        deploy_agent(uri)
