from langgraph.graph import StateGraph, END
from agents import ResumeProcessor, JDProcessor, Coordinator
from schemas.base import AgentState
from logger.logger import log_info, log_debug, log_error,log_warn

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
            
            if "score_threshold" in initial_state.metadata:
                threshold = initial_state.metadata["score_threshold"]
                if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 100:
                    log_warn(f"Invalid threshold value: {threshold}. Using default 75.0")
                    initial_state.metadata["score_threshold"] = 75.0
                else:
                    log_info(f"Using custom threshold: {threshold}")
            else:
                log_info("No threshold specified, using default 75.0")
                initial_state.metadata["score_threshold"] = 75.0

            result = self.workflow.invoke(initial_state)
            log_debug(f"Results in ATS_Workflow: {result}")

            # Wrap the returned dict back into AgentState
            if not isinstance(result, dict):
                log_error(f"Unexpected result type: {type(result)}")
                return AgentState(scores={})

            final_state = AgentState(**result)

            threshold = final_state.metadata.get("score_threshold", 75.0)
            qualified_count = sum(1 for score in final_state.scores.values() if score >= threshold)
            total_count = len(final_state.scores)
            
            log_info(f"Final scores: {final_state.scores}")
            log_info(f"Qualified resumes: {qualified_count}/{total_count} (threshold: {threshold})")
            
            return final_state

        except Exception as e:
            log_error(f"Workflow error: {str(e)}")
            return AgentState(scores={})
