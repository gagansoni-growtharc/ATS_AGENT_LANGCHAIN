from langchain.prompts import PromptTemplate
from langchain.agents import Tool
from typing import List
from .base import OpenAIAgent
from tools.resume_parser import batch_process_resume_folder, process_resume_pdf
from schemas.base import AgentState
from schemas.resume import ResumeContent
from logger.logger import log_error
from langchain_openai import ChatOpenAI
from langchain.chains.llm import LLMChain

class ResumeProcessor(OpenAIAgent):
    def __init__(self):
        llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
        tools = self._setup_tools()
        prompt = self.create_prompt(tools)
        super().__init__(
            llm_chain=LLMChain(llm=llm, prompt=prompt),
            allowed_tools=[t.name for t in tools],
            tools=tools
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
            """,
            input_variables=["input", "tools", "tool_names"],
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
                tool_names=", ".join([t.name for t in self.tools])
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