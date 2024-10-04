from queue import Queue
from fastapi import WebSocket, WebSocketDisconnect
import numpy as np
import asyncio
import uuid

# Dictionary to store queues and session info for each synchronous_id
streams = {}

app = FastAPI()
@app.websocket("/speech")
async def synthesize_speech(
    ws: WebSocket,
    model: Annotated[ModelName, Query()] = config.tts_model,
    voice: Annotated[ModelName, Query()] = config.tts_speaker,
    language: Annotated[Language | None, Query()] = config.default_language,
    response_format: Annotated[ResponseFormat, Query()] = config.default_response_format,
    temperature: Annotated[float, Query()] = 0.0,
    synchronous_id: Annotated[str | None, Query()] | None = None,
) -> None:
    speaker = voice
    await ws.accept()

    # Generate a unique synchronous_id if not provided
    if synchronous_id is None:
        synchronous_id = str(uuid.uuid4())
        logger.info(f"Generated new synchronous ID: {synchronous_id}")
    else:
        logger.info(f"Received synchronous ID: {synchronous_id}")

    # Create a new queue and audio buffer for this synchronous_id if not exists
    if synchronous_id not in streams:
        streams[synchronous_id] = {
            'queue': Queue(),
            'audio_buffer': [],
            'sequence_number': 0
        }

    try:
        # Initialize TTS model
        tts = tts_backup  # or load_speaker(model)

        while True:
            if ws.client_state == WebSocketState.DISCONNECTED:
                break

            # Receive new text data from the client
            text_new = await ws.receive_text()
            logger.debug(f"Received {len(text_new)} characters of text data")

            # Store text in the queue for this synchronous_id
            streams[synchronous_id]['queue'].put_nowait(text_new)

            # Process the queue and generate audio
            text = streams[synchronous_id]['queue'].get()
            audio_data = tts.tts(text, speaker=speaker, language=language, split_sentences=False)
            chunk_size = 2048  # Adjust chunk size as needed

            # Iterate over audio data and send in chunks with sequence numbers
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                audio_chunk = (np.array(chunk) * config.tts_sample_rate).astype(np.int16).tobytes()

                # Add a sequence number for each chunk
                sequence_number = streams[synchronous_id]['sequence_number']
                streams[synchronous_id]['sequence_number'] += 1

                # Create a dictionary to send both the chunk and sequence number
                await ws.send_bytes(audio_chunk)

            # Check if client is still connected, otherwise break the loop
            if ws.client_state != WebSocketState.CONNECTED:
                break

    except WebSocketDisconnect:
        logger.info(f"Client disconnected with synchronous ID: {synchronous_id}")
    except Exception as e:
        logger.error(f"Error: {e}. {traceback.format_exc()}")

    # Clean up after disconnect
    if ws.client_state != WebSocketState.DISCONNECTED:
        logger.info("Closing the connection.")
        await ws.close()

    # Optionally remove the synchronous_id data to release memory
    if synchronous_id in streams:
        del streams[synchronous_id]


if __name__ == "__main__":
    import uvicorn

    from whisper.audio_task import TaskConfig

    if config.enable_ui:
        import gradio as gr

        from whisper.audio_task import TaskConfig
        from whisper.stt import create_gradio_demo

        app = gr.mount_gradio_app(
            app, create_gradio_demo(config, TaskConfig()), path="/", show_error=False, root_path="/audio"
        )
    uvicorn.run(app, host="0.0.0.0", port=5018)
