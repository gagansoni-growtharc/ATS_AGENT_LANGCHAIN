from langgraph.graph import StateGraph, END
from agents import ResumeProcessor, JDProcessor, Coordinator
from schemas.base import AgentState
from logger.logger import log_info, log_debug, log_error

class ATSWorkflow:
    def __init__(self):
        log_info("ATS Workflow Started")
        self.graph = StateGraph(AgentState)
        self.resume_processor = ResumeProcessor()
        self.jd_processor = JDProcessor()
        self.coordinator = Coordinator()
        
        self._build_graph()
        # Compile the graph after building it
        self.workflow = self.graph.compile()
        log_debug("Graph built and compiled")

    def _build_graph(self):
        log_debug("Building Graph")
        self.graph.add_node("parse_jd", self.jd_processor.process)
        self.graph.add_node("process_resumes", self.resume_processor.process)
        self.graph.add_node("score_and_move", self.coordinator.process)
        
        self.graph.add_edge("parse_jd", "process_resumes")
        self.graph.add_edge("process_resumes", "score_and_move")
        self.graph.add_edge("score_and_move", END)
        self.graph.set_entry_point("parse_jd")
        
    def invoke(self, initial_state: AgentState) -> AgentState:
        # Use the compiled workflow for invocation
        result = self.workflow.invoke(initial_state)
        
        # Convert the result to a proper AgentState if needed
        if hasattr(result, 'scores'):
            # Already has scores attribute
            return result
        elif hasattr(result, 'values'):
            # Result is a dictionary-like object, extract the values and create a new AgentState
            try:
                final_state = result.values()[-1]  # Get the last state from the workflow
                return final_state
            except (IndexError, AttributeError):
                # If we can't extract values, create a default AgentState
                log_error("Failed to extract values from workflow result")
                return AgentState(scores={})
        else:
            # Fall back to returning result directly
            return result