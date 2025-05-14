from langchain.agents import Agent
from langchain.chains.llm import LLMChain
from langchain.prompts import PromptTemplate
from langchain.agents.output_parsers import JSONAgentOutputParser
from abc import ABC, abstractmethod
from typing import List, Optional

class OpenAIAgent(Agent, ABC):
    def __init__(
        self,
        llm_chain: LLMChain,
        allowed_tools: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            llm_chain=llm_chain,
            allowed_tools=allowed_tools or [],
            **kwargs
        )
        self.tools = kwargs.get("tools", [])
    
    @abstractmethod
    def create_prompt(self, tools: list) -> PromptTemplate:
        """Create the agent's prompt template"""
        pass

    @classmethod
    def from_llm_and_tools(
        cls,
        llm,
        tools: list,
        prompt: PromptTemplate,
        **kwargs
    ):
        llm_chain = LLMChain(llm=llm, prompt=prompt)
        tool_names = [tool.name for tool in tools]
        return cls(
            llm_chain=llm_chain,
            allowed_tools=tool_names,
            tools=tools,
            **kwargs
        )
    
    @property
    @abstractmethod
    def llm_prefix(self) -> str:
        pass
    
    @property
    @abstractmethod
    def observation_prefix(self) -> str:
        pass
    
    def _get_default_output_parser(self) -> JSONAgentOutputParser:
        return JSONAgentOutputParser()