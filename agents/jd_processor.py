from .base import OpenAIAgent
from tools.jd_parser import parse_job_description_content
from schemas.jd import JDParsingInput
from schemas.base import AgentState
import logging
import fitz  # PyMuPDF for PDF handling
from pathlib import Path
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains.llm import LLMChain
from langchain.agents.output_parsers import JSONAgentOutputParser
from logger.logger import log_info, log_debug, log_error


class JDProcessor(OpenAIAgent):
    def __init__(self):
        # Initialize LLM
        llm = ChatGroq(api_key="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",model="llama3-70b-8192", temperature=0)
        
        # Setup tools
        tools = [parse_job_description_content]
        
        # Create prompt
        prompt = self.create_prompt(tools)
        
        # Initialize LLM chain
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        
        # Create output parser
        output_parser = JSONAgentOutputParser()
        
        # Call parent constructor
        super().__init__(
            llm_chain=llm_chain,
            allowed_tools=[tool.name for tool in tools],
            tools=tools,
            output_parser=output_parser
        )
        
    def create_prompt(self, tools) -> PromptTemplate:
        return PromptTemplate(
            template="""
            You are a job description parser. Analyze the following job description content:
            {jd_content}
            
            Extract key information including job title, required skills, 
            responsibilities, and qualifications.
            
            Available Tools:
            {tools}
            
            Use the following format:
            Thought: Consider what to do
            Action: The tool to use
            Action Input: The input to the tool
            Observation: The tool's output
            ... (repeat as needed)
            Final Answer: The parsed job description data
            Agent Scratchpad :{agent_scratchpad}
            """,
            input_variables=["jd_content", "tools", "agent_scratchpad"],
            partial_variables={
                "tools": "\n".join([f"{t.name}: {t.description}" for t in tools])
            }
        )
    
    @property
    def llm_prefix(self) -> str:
        return "Thought:"
    
    @property
    def observation_prefix(self) -> str:
        return "Observation:"
        
    def process(self, state: AgentState) -> AgentState:
        try:
            jd_path = state.metadata.get("jd_path")
            jd_path = Path(jd_path)
            # Use PyMuPDF (fitz) to reliably extract text from PDF
            try:
                if not jd_path.exists():
                    log_error("File not found", path=str(jd_path))
                    return {"status": "error", "message": "File not found"}
                with fitz.open(jd_path) as doc:
                    jd_content = ""
                    for page in doc:
                        jd_content += page.get_text()
            except UnicodeDecodeError:
                # Fall back to latin-1 encoding if UTF-8 fails
                with open(jd_path, "r", encoding="latin-1") as f:
                    jd_content = f.read()
                
            
            # Pass parameters directly, not through a params dictionary
            input_obj = {
                "jd_content": jd_content,
                "parse_mode": "full"
            }
            
            parsed = parse_job_description_content.invoke(input_obj)

            state_data = state.model_dump(exclude={"jd_content", "metadata"})
            return AgentState(
                **state_data,
                jd_content=jd_content,
                metadata={
                    **state.metadata,
                    "parsed_jd": parsed["result"]
                }
            )
        except Exception as e:
            log_error(f"JD processing failed: {str(e)}")
            return state