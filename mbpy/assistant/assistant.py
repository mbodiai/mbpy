# First, import required modules and classes
import asyncio
from collections.abc import AsyncIterator
from itertools import chain
import json
import traceback
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict

import anyio
import anyio.to_thread
import gradio as gr
from gradio import ChatInterface
from mbodied.types.sample import Sample
from openai import AsyncAssistantEventHandler, AsyncOpenAI
from openai.types.beta.assistant_stream_event import AssistantStreamEvent, ThreadRunRequiresAction
from openai.types.beta.threads.run import Run
from openai.types.beta.threads.run_submit_tool_outputs_params import ToolOutput
from openai.types.beta.threads.runs import ToolCall, ToolCallDelta, RunStepDelta
from rich.console import Console
from tools import (
    ToolOutput as CommandResponse,
)
from tools import (
    dispatch_coding_assistant,
    execute_code_with_markdown,
    pip_install,
    run_shell_command,
)
from typing_extensions import override

from mbpy.assistant.tools import TOOLS

console = Console(style="bold light_goldenrod2")
print = console.print


class DiscreteAction(Sample):
    HAND_FORWARD: bool = False
    HAND_BACKWARD: bool = False
    HAND_LEFT: bool = False
    HAND_RIGHT: bool = False
    HAND_UP: bool = False
    HAND_DOWN: bool = False
    HAND_PITCH_DOWN: bool = False
    HAND_PITCH_UP: bool = False
    HAND_YAW_LEFT: bool = False
    HAND_YAW_RIGHT: bool = False
    HAND_ROLL_LEFT: bool = False
    HAND_ROLL_RIGHT: bool = False
    HAND_GRIP: bool = False
    HAND_RELEASE: bool = False
    HAND_STOP: bool = False
    HAND_RESET: bool = False

    TILT_HEAD_UP: bool = False
    TILT_HEAD_DOWN: bool = False
    TILT_HEAD_LEFT: bool = False
    TILT_HEAD_RIGHT: bool = False
    TILT_HEAD_STOP: bool = False


class WorldState(Sample):
    STATUS: str = "NEUTRAL"
    OBSERVATION: str = "NOT_SET"
    ACTION: str = "NOT_SET"


# Initialize the OpenAI client
client = AsyncOpenAI(api_key="sk-proj-6BvmNFHPGkJHT9NLyV04T3BlbkFJDps9Ydy01tgAwKcEYvOK")


SUPERVISOR = """
Your goal is to evaluate an event and update the global status accordings. Events are given in the form:

TASK: {TASK}, OBSERVATION: {OBSERVATION}, ACTION: {ACTION}
"

Update the global status in reference to successful completion of the task. The status can be one of the following:

- OPTIMAL
- SUB_OPTIMAL
- NEUTRAL
- NEGATIVE
- CATASTROPHIC

If it is catastrophic, then the agent should cease all movement and stop the task urgently. Examples of this are if the agent
is about to collide with something. If it is negative then the agent should slow down but continue and reevaluate the 
the situation by querying tools then formulating a new plan. If it is neutral then the agent should continue at the same pace 
but also re-evaluate and re-plan. Return exactly one word being the status and nothing else.
"""


CODER = """You are a helpful assistant. When asked to write code always write it as a python function unless specified otherwise. Ensure it includes google style docs, and complies with RUFF guidelines including:
- return types
- multiline docstring with open quotes on sameline
-closed quotes on a new line
-new line between single line description and further details. 
-ensure each docstring includes an example.

Below the function do the following:
- write a unit test
"""

EXECUTOR = """ You are an execution assistant. Use the provided world state and action to execute an
action. 
"""


# Replace with actual import or definition of AsyncAssistantEventHandler and client
# from your_project import AsyncAssistantEventHandler, client, PYTHON_RUN, execute_python

# Initialize assistant as None
assistant = None

# Initialize HISTORY
HISTORY = []

# First, create a mapping between function names and actual function implementations
FUNCTION_MAP: Dict[str, Callable[..., ToolOutput]] = {
    "run_shell_command": run_shell_command,
    "pip_install": pip_install,
    "dispatch_coding_assistant": dispatch_coding_assistant,
    "execute_code_with_markdown": execute_code_with_markdown,
}


# Define the EventHandler class as before
class EventHandler(AsyncAssistantEventHandler):
    def __init__(self, *args, **kwargs):
        self.tool_outputs: list[ToolOutput] = []
        super().__init__(*args, **kwargs)
        
    async def on_tool_call_created(self, tool_call) -> None:
        print(f"Tool call created: {tool_call.type}")

        if tool_call.type == "function":
            print(f"Function name: {tool_call.function.name}")
            print(f"Function arguments: {tool_call.function.arguments}")

    async def on_tool_call_delta(self, delta: ToolCallDelta, snapshot: ToolCall) -> None:
        if delta.type == "function" and delta.function.arguments:
            content = f"\nassistant {delta.function.name}:  {delta.function.arguments}\n"
            print(content)
            print(f"Output: {snapshot}")

    async def on_tool_call_done(self, tool_call: ToolCall):
        print(f"Tool call done: {tool_call}")
        if tool_call.type == "function":
            print(f"Function name: {tool_call.function.name}")
            print(f"Function arguments: {tool_call.function.arguments}")

        return  await self.handle_requires_action(self.current_run, self.current_run.id)

    
    
          
    # async def on_event(self, event: AssistantStreamEvent) -> None:
    #     if event == ThreadRunRequiresAction:
    #         print('Thread run requires action')
    #         await self.handle_requires_action(event.data, event.data.run_id)

    # async def submit_tool_outputs(self, tool_outputs: list[ToolOutput], run_id) -> str:
    #     if self.current_run is None or self.current_run.thread_id is None:
    #         raise ValueError("Current run or thread ID is not set.")
    #     thread_id = self.current_run.thread_id
    #     async with client.beta.threads.runs.submit_tool_outputs_stream(
    #         thread_id=thread_id,
    #         run_id=run_id,
    #         tool_outputs=tool_outputs,
    #     ) as stream:
    #         response = ""
    #         print("Tool outputs:")
    #         async for text in stream.text_deltas:
    #             print(text, end="")
    #             response += text
    #             yield response
    #         print()
    #     return

    async def handle_requires_action(self, data: Run, run_id: str) -> list[ToolOutput]:
        tool_outputs = []

        for tool in data.required_action.submit_tool_outputs.tool_calls:
            if tool.type == "function":
                function_name = tool.function.name
                function_to_call = FUNCTION_MAP.get(function_name)
                print(f"Calling function: {function_name} with parameters: {tool.function.arguments}")

                if function_to_call:
                    try:
                        # Call the appropriate function with parameters
                        output: CommandResponse = await anyio.to_thread.run_sync(
                            function_to_call, *dict(json.loads(tool.function.arguments)).values()
                        )
                        self.tool_outputs.append({"tool_call_id": tool.id, **output})
                    except Exception as e:
                        print(f"Error executing tool {tool.id}: {e}")
                        traceback.print_exc()
                        self.tool_outputs.append({"tool_call_id": tool.id, **output})
                else:
                    # Handle unknown function names
                    error_message = f"Unknown function '{function_name}'"
                    print(error_message)
                    self.tool_outputs.append({"tool_call_id": tool.id, **output})

        async with client.beta.threads.runs.submit_tool_outputs_stream(
            thread_id=data.thread_id,
            run_id=run_id,
            tool_outputs=self.tool_outputs,
        ) as stream:
            await stream.until_done()

        return self.tool_outputs
        



async def get_assistant():
    return await client.beta.assistants.create(
        instructions="You are an execution assistant. Use the provided functions to fulfill the user's requests.",
        model="gpt-4o",  # Use the appropriate model for text-based tasks
        tools=TOOLS,
    )


def not_none(value: Dict[str,Any]):
    return (
        {k: v for k, v in value.items() if not_none(v)}
        if value is not None and hasattr(value, "items")
        else value
        if value is not None
        else None
    )

async def stream_deltas(manager: EventHandler) -> AsyncIterator[str]:
    async for event in manager:
        if event.event == "thread.message.delta":

            for content_delta in event.data.delta.content or []:
                if content_delta.type == "text" and content_delta.text and content_delta.text.value:
                    yield content_delta.text.value
        elif event.event == "thread.run.step.completed":
            for tool_output in manager.tool_outputs:
                yield tool_output.output


async def predict(message, history) -> AsyncGenerator[str, None]:
    global assistant
    global HISTORY
    print(message)
    print(history)
    print(history[-1] if len(history) > 0 else None)
    # Update HISTORY with the latest conversation
    HISTORY.append(not_none(history[-2])) if len(history) > 1 else None
    HISTORY.append(not_none(history[-1])) if len(history) > 0 else None

    response = ""
    try:
        # Create a new thread with the updated history
        thread = await client.beta.threads.create(messages=HISTORY + [{"role": "user", "content": message}])
        handler = EventHandler()
        # Stream the assistant's response
        async with client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=assistant.id,
            event_handler=handler,
        ) as stream:
            async for text in stream_deltas(stream):
                response += text
                yield response

    except Exception as e:
        print(e)
        traceback.print_exc()
        yield "Sorry, I'm having trouble understanding your question." + str(e) + "\n" + traceback.format_exc()

    # Add a final yield to ensure the generator doesn't raise StopAsyncIteration
    if not response and not handler.tool_outputs:
        yield "No response was generated."
    elif handler.tool_outputs:
        for tool in handler.tool_outputs:
            yield tool["output"]


def get_demo():
    from gradio.themes.utils import colors

    mbodi_color = colors.Color(
        c50="#fde8e8",
        c100="#f9b9b9",
        c200="#f58b8b",
        c300="#f15c5c",
        c400="#ee2e2e",
        c500="#ed3d5d",  # Main theme color
        c600="#b93048",
        c700="#852333",
        c800="#51171f",
        c900="#1e0a0a",
        c950="#0a0303",
        name="mbodi",
    )

    THEME = gr.themes.Soft(
        primary_hue=mbodi_color,
        secondary_hue="stone",
        neutral_hue="zinc",
        font="arial",
        font_mono=["consolas"],
    )
    return ChatInterface(fn=predict, theme=THEME, type="messages", multimodal=True)


async def main():
    global assistant

    # Initialize the assistant
    assistant = await get_assistant()

    # Ensure the assistant is available
    while assistant is None:
        await asyncio.sleep(1)
        assistant = await get_assistant()

    # Define the ChatInterface with the async predict function
    with get_demo() as demo:
        demo.queue().launch(server_name="0.0.0.0", server_port=4005)


# Run the main function using asyncio
if __name__ == "__main__":
    asyncio.run(main())
