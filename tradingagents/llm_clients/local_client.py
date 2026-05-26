import os
import requests
import re
import json
import uuid
from typing import Any, List, Optional, Sequence
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun

from .base_client import BaseLLMClient


class LocalChatModel(BaseChatModel):
    """Custom LangChain BaseChatModel to invoke the user's custom local LLM server."""
    
    model_name: str
    base_url: str
    bound_tools: List[Any] = []

    def __init__(self, model_name: str, base_url: str, bound_tools: List[Any] = None, **kwargs):
        super().__init__(
            model_name=model_name,
            base_url=base_url,
            bound_tools=bound_tools or [],
            **kwargs
        )

    @property
    def _llm_type(self) -> str:
        return "local_custom"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        """Bind tools to the model."""
        return LocalChatModel(
            model_name=self.model_name,
            base_url=self.base_url,
            bound_tools=list(tools),
            **kwargs
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Extract system prompt and user input
        system_parts = []
        input_parts = []
        
        for msg in messages:
            role = ""
            content = msg.content
            
            # Identify message role
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
            if isinstance(msg, SystemMessage):
                role = "system"
            elif isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, ToolMessage):
                role = "tool"
            else:
                role = "user"
                
            if role == "system":
                system_parts.append(content)
            elif role == "assistant":
                if msg.tool_calls:
                    # If assistant made a tool call previously, format it nicely
                    for tc in msg.tool_calls:
                        input_parts.append(f"Assistant: Called tool {tc['name']} with args {tc['args']}.")
                if content:
                    input_parts.append(f"Assistant: {content}")
            elif role == "tool":
                input_parts.append(f"Tool Result ({msg.name}): {content}")
            else:
                input_parts.append(f"User: {content}")
                
        system_prompt = "\n".join(system_parts) if system_parts else "You are a helpful financial trading AI assistant."
        
        # If tools are bound, inject tool descriptions and execution schema
        if self.bound_tools:
            tool_instructions = "\n\n### Available Tools\nYou have access to the following tools for retrieving financial data:\n"
            for tool in self.bound_tools:
                name = getattr(tool, "name", getattr(tool, "__name__", str(tool)))
                description = getattr(tool, "description", "")
                args = getattr(tool, "args", "")
                tool_instructions += f"- `{name}`: {description}. Arguments schema: {args}\n"
                
            tool_instructions += (
                "\nTo execute a tool call, you MUST respond ONLY with a JSON block in this exact format:\n"
                "```json\n"
                "{\n"
                '  "tool": "tool_name",\n'
                '  "args": {"arg_name": "value"}\n'
                "}\n"
                "```\n"
                "Do not write any other text, pleasantries, or reasoning when you decide to call a tool. Just output the JSON block."
            )
            system_prompt += tool_instructions

        input_text = "\n".join(input_parts) if input_parts else "Please analyze the financial data."
        
        payload = {
            "model": self.model_name,
            "system_prompt": system_prompt,
            "input": input_text
        }
        
        # Call the local API
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=300)
            response.raise_for_status()
            response_json = response.json()
            
            # Extract output
            raw_text = ""
            output_blocks = response_json.get("output", [])
            for block in output_blocks:
                if isinstance(block, dict) and block.get("type") == "message":
                    raw_text = block.get("content", "").strip()
                    break
            
            if not raw_text:
                if "response" in response_json:
                    raw_text = response_json["response"]
                elif "choices" in response_json and len(response_json["choices"]) > 0:
                    choice = response_json["choices"][0]
                    if isinstance(choice, dict):
                        if "message" in choice and isinstance(choice["message"], dict):
                            raw_text = choice["message"].get("content", "")
                        else:
                            raw_text = choice.get("text", "")
                elif "text" in response_json:
                    raw_text = response_json["text"]
                elif "message" in response_json:
                    raw_text = response_json["message"]
                elif isinstance(response_json, str):
                    raw_text = response_json
                else:
                    raw_text = str(response_json)
                    
        except Exception as e:
            raw_text = f"Error calling local LLM API: {str(e)}"

        # Attempt to parse any JSON block for tool calls
        tool_calls = []
        json_match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
        
        if not json_match:
            # Check if raw_text itself is a JSON object
            stripped = raw_text.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                raw_text_clean = stripped
            else:
                raw_text_clean = None
        else:
            raw_text_clean = json_match.group(1).strip()
            
        if raw_text_clean:
            try:
                parsed_json = json.loads(raw_text_clean)
                if "tool" in parsed_json and "args" in parsed_json:
                    tool_call = {
                        "name": parsed_json["tool"],
                        "args": parsed_json["args"],
                        "id": "call_" + str(uuid.uuid4()).replace("-", ""),
                        "type": "tool_call"
                    }
                    tool_calls.append(tool_call)
            except Exception:
                pass
                
        if tool_calls:
            # We found a tool call, so return an AIMessage with empty content and the tool call
            ai_message = AIMessage(content="", tool_calls=tool_calls)
        else:
            # Standard text generation report
            ai_message = AIMessage(content=raw_text)
            
        return ChatResult(generations=[ChatGeneration(message=ai_message)])


class LocalClient(BaseLLMClient):
    """Client for local custom LLM API."""

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return the custom LocalChatModel."""
        url = self.base_url or "http://localhost:8000/api/v1/chat"
        return LocalChatModel(model_name=self.model, base_url=url)

    def validate_model(self) -> bool:
        """Any local model is valid."""
        return True
