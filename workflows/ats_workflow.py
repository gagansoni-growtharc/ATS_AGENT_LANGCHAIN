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
        try:
            # Use the compiled workflow for invocation
            result = self.workflow.invoke(initial_state)
            
            # Extract the final state safely
            if isinstance(result, AgentState):
                # Result is already an AgentState
                return result
            elif hasattr(result, 'values') and callable(result.values):
                # Result is dict-like, convert values to list to access last item
                values_list = list(result.values())
                if values_list:
                    final_state = values_list[-1]
                    return final_state if isinstance(final_state, AgentState) else AgentState(scores={})
                else:
                    return AgentState(scores={})
            else:
                # Fall back to default state
                log_error("Unexpected workflow result format")
                return AgentState(scores={})
        except Exception as e:
            log_error(f"Workflow invoke error: {str(e)}")
            return AgentState(scores={})