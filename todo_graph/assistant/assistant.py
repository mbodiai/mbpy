# First, import required modules and classes
import asyncio
import os
import traceback
from typing import AsyncGenerator, Coroutine

import anyio
import gradio as gr
from gradio import ChatInterface
from mbodied.types.sample import Sample
from openai import AsyncAssistantEventHandler, AsyncOpenAI
from typing_extensions import override

from mbpy.assistant.tools import dispatch_coding_assistant, execute_code_with_markdown, pip_install, run_shell_command, TOOLS


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
    STATUS: str = 'NEUTRAL'
    OBSERVATION: str = 'NOT_SET'
    ACTION: str = 'NOT_SET'
    

# Initialize the OpenAI client
client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))




# Initialize assistant as None
assistant = None

# Initialize HISTORY
HISTORY = []

# First, create a mapping between function names and actual function implementations
FUNCTION_MAP = {
    "run_shell_command": run_shell_command,
    "pip_install": pip_install,
    "dispatch_coding_assistant": dispatch_coding_assistant,
    "execute_code_with_markdown": execute_code_with_markdown,
}


# Define the EventHandler class as before
class EventHandler(AsyncAssistantEventHandler):
    async def on_tool_call_created(self, tool_call) -> None:
        print(f'Tool call created: {tool_call.type}')

        if tool_call.type == 'function':
            print(f'Function name: {tool_call.function.name}')
            print(f'Function arguments: {tool_call.function.arguments}')

    async def on_tool_call_delta(self, delta, snapshot) -> None:
        if delta.type == 'function' and delta.function.arguments:
            content = f'\nassistant {delta.function.name}:  {delta.function.arguments}\n'
            print(content)

    async def submit_tool_outputs(self, tool_outputs, run_id) -> str:
        if self.current_run is None or self.current_run.thread_id is None:
            raise ValueError('Current run or thread ID is not set.')
        thread_id = self.current_run.thread_id
        async with client.beta.threads.runs.submit_tool_outputs_stream(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_outputs,
            event_handler=EventHandler(),
        ) as stream:
            response = ''
            async for text in stream.text_deltas:
                print(text, end='', flush=True)
                response += text
            print()
        return response

    async def handle_requires_action(self, data, run_id) -> None:
        tool_outputs = []

        for tool in data.required_action.submit_tool_outputs.tool_calls:
            if tool.type == "function":
                function_name = tool.function.name
                function_to_call = FUNCTION_MAP.get(function_name)

                if function_to_call:
                    try:
                        # Call the appropriate function with parameters
                        output = await anyio.to_thread.run_sync(function_to_call, **tool.parameters)
                        tool_outputs.append({"tool_call_id": tool.id, "output": output})
                    except Exception as e:
                        print(f"Error executing tool {tool.id}: {e}")
                        traceback.print_exc()
                        tool_outputs.append({"tool_call_id": tool.id, "error": str(e)})
                else:
                    # Handle unknown function names
                    error_message = f"Unknown function '{function_name}'"
                    print(error_message)
                    tool_outputs.append({"tool_call_id": tool.id, "error": error_message})

        await self.submit_tool_outputs(tool_outputs, run_id)

async def get_assistant():
    return await client.beta.assistants.create(
        instructions="You are an execution assistant. Use the provided functions to fulfill the user's requests.",
        model='gpt-4o',  # Use the appropriate model for text-based tasks
        tools=TOOLS,
    )

async def predict(message, history) -> AsyncGenerator[str, None]:
    global assistant
    global HISTORY

    # Update HISTORY with the latest conversation
    if len(history) > 0:
        HISTORY.append({'role': 'user', 'content': history[-1][0]})
        HISTORY.append({'role': 'assistant', 'content': history[-1][1]})

    response = ''
    try:
        # Create a new thread with the updated history
        thread = await client.beta.threads.create(messages=HISTORY + [{'role': 'user', 'content': message}])
        # Stream the assistant's response
        async with client.beta.threads.runs.stream(
            thread_id=thread.id,
            assistant_id=assistant.id,
            event_handler=EventHandler(),
        ) as stream:
            async for text in stream.text_deltas:
                response += text
                yield response  # Ensure we yield here
    except Exception as e:
        print(e)
        traceback.print_exc()
        yield "Sorry, I'm having trouble understanding your question."  # Ensure we yield here

    # Add a final yield to ensure the generator doesn't raise StopAsyncIteration
    if not response:
        yield 'No response was generated.'

async def main():
    global assistant

    # Initialize the assistant
    assistant = await get_assistant()

    # Ensure the assistant is available
    while assistant is None:
        await asyncio.sleep(1)
        assistant = await get_assistant()

    # Define the ChatInterface with the async predict function
    with ChatInterface(fn=predict) as demo:
        demo.queue().launch(server_name='0.0.0.0', server_port=4004)


# Run the main function using asyncio
if __name__ == '__main__':
    asyncio.run(main())