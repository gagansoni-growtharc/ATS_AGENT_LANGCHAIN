from pathlib import Path
from langchain.prompts import PromptTemplate
from langchain.agents import Tool
from typing import List, Dict, Any
from .base import OpenAIAgent
from tools.resume_parser import batch_process_resume_folder
from tools.metadata_handling import find_matching_metadata,load_metadata
from schemas.base import AgentState
from schemas.resume import ResumeContent, ResumeMetadata
from logger.logger import log_error,log_debug
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
        batch_process_resume_folder,find_matching_metadata,load_metadata
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
            resume_folder = state.metadata.get("resume_folder")
            metadata_folder = state.metadata.get("metadata_folder")
            
            # Pass parameters directly without wrapping in params
            batch_result = batch_process_resume_folder.invoke({
                "folder_path": resume_folder,
                "extension": "pdf",
                "batch_size": 100
                
            })
            
            # Process each resume individually to ensure proper extraction
            processed = []
            if batch_result.get("status") == "success":
                for file_info in batch_result["processed_files"]:
                    resume_name = Path(file_info["file_path"]).stem
                    resume_meta = {}
                    if metadata_folder:
                        meta_path = f"{metadata_folder}/{resume_name}.json"
                        meta_result = load_metadata.invoke({"metadata_path": meta_path})
                        if meta_result["status"] == "success":
                            resume_meta = meta_result.get("metadata", {})
                            log_debug(f"metadata found for: {resume_name}: {resume_meta}")
                        else:
                            log_debug(f"No metadata found for: {resume_name}")

                    processed.append(
                        ResumeContent(
                            text=file_info["content"],
                            file_path=file_info["file_path"],
                            metadata=resume_meta
                        )
                    )
            
            # Use model_dump from the original state to create a new one
            state_data = state.model_dump()
            state_data["resumes"] = processed
            return AgentState(**state_data)
        
        except Exception as e:
            log_error(f"Resume processing failed: {str(e)}")
            return state