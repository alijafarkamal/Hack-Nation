"""
MLflow tracing integration for agent reasoning transparency.
Captures citations and decision traces for NGO auditing.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    mlflow = None
    MlflowClient = None

from config import Config


class MLflowTracing:
    """Manages MLflow experiment tracking and reasoning traces."""
    
    def __init__(self, experiment_name: Optional[str] = None):
        """
        Initialize MLflow tracking.
        
        Args:
            experiment_name: Name of MLflow experiment (uses config default if None)
        """
        self.config = Config()
        
        if not MLFLOW_AVAILABLE:
            print("⚠️  MLflow not available. Tracing disabled.")
            self.client = None
            self.current_run_id = None
            return
        
        # Set tracking URI
        mlflow.set_tracking_uri(self.config.MLFLOW_TRACKING_URI)
        
        # Set or create experiment
        self.experiment_name = experiment_name or self.config.MLFLOW_EXPERIMENT_NAME
        
        try:
            mlflow.set_experiment(self.experiment_name)
            print(f"✅ MLflow experiment set: {self.experiment_name}")
        except Exception as e:
            print(f"⚠️  MLflow setup warning: {e}")
        
        self.client = MlflowClient()
        self.current_run_id = None
    
    def start_agent_run(self, agent_name: str, input_data: Dict[str, Any]) -> str:
        """
        Start a new MLflow run for an agent execution.
        
        Args:
            agent_name: Name of the agent (e.g., "parser_agent")
            input_data: Input parameters for the agent
            
        Returns:
            Run ID
        """
        if not MLFLOW_AVAILABLE or self.client is None:
            return "mlflow_disabled"
        
        run = mlflow.start_run(run_name=f"{agent_name}_{datetime.now().isoformat()}")
        self.current_run_id = run.info.run_id
        
        # Log input parameters
        mlflow.log_params({
            "agent_name": agent_name,
            "timestamp": datetime.now().isoformat()
        })
        
        # Log input data as JSON
        mlflow.log_dict(input_data, "input_data.json")
        
        print(f"🚀 Started MLflow run: {self.current_run_id}")
        return self.current_run_id
    
    def log_reasoning_step(
        self, 
        step_name: str, 
        reasoning: str, 
        citations: List[str],
        confidence: float
    ) -> None:
        """
        Log a single reasoning step with citations.
        
        Args:
            step_name: Name of the reasoning step
            reasoning: Natural language explanation of the step
            citations: List of source citations
            confidence: Confidence score (0-1)
        """
        if not MLFLOW_AVAILABLE or self.client is None:
            return
        if not self.current_run_id:
            print("⚠️  No active MLflow run. Call start_agent_run first.")
            return
        
        step_data = {
            "step_name": step_name,
            "reasoning": reasoning,
            "citations": citations,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
        
        # Log as artifact
        mlflow.log_dict(step_data, f"reasoning_steps/{step_name}.json")
        
        # Log confidence metric
        mlflow.log_metric(f"confidence_{step_name}", confidence)
    
    def log_citation(
        self, 
        claim: str, 
        source: str, 
        line_number: Optional[int] = None
    ) -> None:
        """
        Log a specific citation for audit trail.
        
        Args:
            claim: The extracted claim/fact
            source: Source document or table
            line_number: Optional line number in source
        """
        if not MLFLOW_AVAILABLE or self.client is None:
            return
        
        citation = {
            "claim": claim,
            "source": source,
            "line_number": line_number,
            "timestamp": datetime.now().isoformat()
        }
        
        # Store in a list for this run
        mlflow.log_dict(
            citation, 
            f"citations/citation_{datetime.now().timestamp()}.json"
        )
    
    def log_medical_desert_detection(
        self, 
        region: str, 
        deserts: List[Dict[str, Any]],
        analysis: Dict[str, Any]
    ) -> None:
        """
        Log medical desert detection results.
        
        Args:
            region: Region analyzed
            deserts: List of detected medical deserts
            analysis: Full analysis results
        """
        if not MLFLOW_AVAILABLE or self.client is None:
            return
        
        mlflow.log_param("analyzed_region", region)
        mlflow.log_metric("desert_count", len(deserts))
        
        # Log full analysis
        mlflow.log_dict(analysis, "medical_desert_analysis.json")
        
        # Log desert locations
        for i, desert in enumerate(deserts):
            mlflow.log_dict(desert, f"deserts/desert_{i}.json")
    
    def end_agent_run(
        self, 
        status: str = "success", 
        output_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        End the current MLflow run.
        
        Args:
            status: Run status ("success", "failed", "warning")
            output_data: Final output data from the agent
        """
        if not MLFLOW_AVAILABLE or self.client is None:
            return
        if not self.current_run_id:
            print("⚠️  No active MLflow run to end.")
            return
        
        # Log final status
        mlflow.log_param("status", status)
        
        # Log output data
        if output_data:
            mlflow.log_dict(output_data, "output_data.json")
        
        # End the run
        mlflow.end_run()
        
        print(f"✅ MLflow run ended: {self.current_run_id} (status: {status})")
        self.current_run_id = None
    
    def get_run_traces(self, run_id: str) -> Dict[str, Any]:
        """
        Retrieve all traces for a specific run.
        
        Args:
            run_id: MLflow run ID
            
        Returns:
            Dictionary with all run artifacts and metrics
        """
        if not MLFLOW_AVAILABLE or self.client is None:
            return {}
        
        run = self.client.get_run(run_id)
        
        return {
            "run_id": run_id,
            "status": run.info.status,
            "start_time": run.info.start_time,
            "end_time": run.info.end_time,
            "params": run.data.params,
            "metrics": run.data.metrics,
            "artifacts": self.client.list_artifacts(run_id)
        }
    
    def create_trace_report(
        self, 
        run_id: str, 
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate a human-readable trace report for NGO auditing.
        
        Args:
            run_id: MLflow run ID
            output_path: Optional path to save report
            
        Returns:
            Markdown-formatted report
        """
        traces = self.get_run_traces(run_id)
        
        report = f"""# Agent Execution Trace Report
        
## Run Information
- **Run ID**: {run_id}
- **Status**: {traces['status']}
- **Start Time**: {datetime.fromtimestamp(traces['start_time']/1000)}
- **End Time**: {datetime.fromtimestamp(traces['end_time']/1000) if traces['end_time'] else 'In Progress'}

## Parameters
{self._format_dict(traces['params'])}

## Metrics
{self._format_dict(traces['metrics'])}

## Artifacts
{self._format_artifacts(traces['artifacts'])}

---
*Generated for NGO audit trail compliance*
"""
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
            print(f"📄 Trace report saved to: {output_path}")
        
        return report
    
    def _format_dict(self, data: Dict[str, Any]) -> str:
        """Format dictionary as markdown list."""
        return "\n".join([f"- **{k}**: {v}" for k, v in data.items()])
    
    def _format_artifacts(self, artifacts: List[Any]) -> str:
        """Format artifact list as markdown."""
        return "\n".join([f"- {artifact.path}" for artifact in artifacts])


if __name__ == "__main__":
    # Quick test
    tracing = MLflowTracing()
    print("✅ MLflow tracing initialized successfully")
