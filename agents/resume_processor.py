from langchain.prompts import PromptTemplate
from langchain.agents import Tool
from typing import List
from .base import OpenAIAgent
from tools.resume_parser import batch_process_resume_folder, process_resume_pdf
from schemas.base import AgentState
from schemas.resume import ResumeContent
from logger.logger import log_error
from langchain_groq import ChatGroq
from langchain.chains.llm import LLMChain
from langchain.agents.output_parsers import JSONAgentOutputParser

class ResumeProcessor(OpenAIAgent):
    def __init__(self):
        # Initialize the LLM
        llm = ChatGroq(api_key="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",model="llama3-70b-8192", temperature=0)

        
        # Setup tools
        tools = self._setup_tools()
        
        # Create the prompt
        prompt = self.create_prompt(tools)
        
        # Create the output parser
        output_parser = JSONAgentOutputParser()
        
        # Initialize the LLM chain
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        
        # Initialize the base class
        super().__init__(
            llm_chain=llm_chain,
            allowed_tools=[t.name for t in tools],
            tools=tools,
            output_parser=output_parser
        )
    
    def _setup_tools(self) -> List[Tool]:
        return [
            Tool(
                name="batch_process_resume_folder",
                func=batch_process_resume_folder,
                description="Process a folder of resume PDFs"
            ),
            Tool(
                name="process_resume_pdf",
                func=process_resume_pdf,
                description="Process a single resume PDF"
            )
        ]

    def create_prompt(self, tools: List[Tool]) -> PromptTemplate:
        tool_names = ", ".join([t.name for t in tools])
        return PromptTemplate(
            template="""
            You are an expert resume processor. Analyze the following resume content:
            {input}
            
            Available Tools:
            {tools}
            
            Use the following format:
            Thought: Consider what to do
            Action: The tool to use (must be one of [{tool_names}])
            Action Input: The input to the tool
            Observation: The tool's output
            ... (repeat as needed)
            Final Answer: The processed resume data in JSON format
            Agent Scratchpad :{agent_scratchpad}
            """,
            input_variables=["input", "tools", "tool_names", "agent_scratchpad"],
            partial_variables={
                "tools": "\n".join([f"{t.name}: {t.description}" for t in tools]),
                "tool_names": tool_names
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
            result = self.llm_chain.run(
                input=state.input,
                tools=self.tools,
                tool_names=", ".join([t.name for t in self.tools]),
                agent_scratchpad=""  # Add this required parameter
            )
            
            processed = [
                ResumeContent(
                    text=item["content"],
                    file_path=item["file_path"],
                    metadata=item.get("metadata")
                ) for item in result["results"]
            ]
            
            return AgentState(
                **state.model_dump(),
                resumes=processed
            )
        except Exception as e:
            log_error(f"Resume processing failed: {str(e)}")
            return state