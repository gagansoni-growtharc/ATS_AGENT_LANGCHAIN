from .base import OpenAIAgent
from tools.jd_parser import parse_job_description_content
from schemas.jd import JDParsingInput
from schemas.base import AgentState
import logging
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains.llm import LLMChain
from langchain.agents.output_parsers import JSONAgentOutputParser  # Added import

logger = logging.getLogger(__name__)

class JDProcessor(OpenAIAgent):
    def __init__(self):
        # Initialize LLM
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        # Setup tools
        tools = [parse_job_description_content]
        
        # Create prompt
        prompt = self.create_prompt(tools)
        
        # Initialize LLM chain
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        
        # Create output parser - Added this line
        output_parser = JSONAgentOutputParser()
        
        # Call parent constructor
        super().__init__(
            llm_chain=llm_chain,
            allowed_tools=[tool.name for tool in tools],
            tools=tools,
            output_parser=output_parser  # Added this parameter
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
            with open(jd_path, "r") as f:
                jd_content = f.read()
                
            parsed = parse_job_description_content({
                "jd_content": jd_content,
                "parse_mode": "full"
            })
            
            return AgentState(
                **state.model_dump(),
                jd_content=jd_content,
                metadata={
                    **state.metadata,
                    "parsed_jd": parsed
                }
            )
        except Exception as e:
            logger.error(f"JD processing failed: {str(e)}")
            return state