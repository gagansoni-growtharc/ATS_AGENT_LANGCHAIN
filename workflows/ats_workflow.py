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
        log_debug("Graph builded")

    def _build_graph(self):
        log_debug("Building Graph")
        self.graph.add_node("parse_jd", self.jd_processor.process)
        self.graph.add_node("process_resumes", self.resume_processor.process)
        self.graph.add_node("score_and_move", self.coordinator.process)
        
        self.graph.add_edge("parse_jd", "process_resumes")
        self.graph.add_edge("process_resumes", "score_and_move")
        self.graph.add_edge("score_and_move", END)
        
    def invoke(self, initial_state: AgentState) -> AgentState:
        return self.graph.invoke(initial_state)