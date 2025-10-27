# Real-Time Audio Transcription WebSocket API

This document describes the WebSocket endpoint for real-time audio transcription using WhisperX and Silero-VAD.

## Overview

The `/audio` WebSocket endpoint enables real-time speech-to-text transcription with automatic voice activity detection (VAD). It's designed for interactive applications like chatbots, voice assistants, and live transcription systems.

### Key Features

- **Real-time transcription** using WhisperX (large-v3 by default)
- **Voice Activity Detection** using Silero-VAD for speech boundary detection
- **Pre-roll buffer** (300ms) to avoid speech truncation at start
- **Minimum utterance length** (1.5s) to filter out false detections
- **Event-based communication** for responsive UX
- **Per-session state management** supporting concurrent connections
- **Automatic resource cleanup** on disconnect

## Connection

### WebSocket URL

```
ws://your-server:8000/audio
```

Or with TLS:

```
wss://your-server:8000/audio
```

### Audio Format Requirements

- **Encoding**: 16-bit PCM (Little Endian)
- **Sample Rate**: 16000 Hz (16 kHz)
- **Channels**: 1 (Mono)
- **Chunk Size**: Flexible, recommended 512-2048 samples (32-128ms at 16kHz)

### Example: Connecting with JavaScript

```javascript
const ws = new WebSocket('ws://localhost:8000/audio');

ws.onopen = () => {
  console.log('Connected to real-time transcription service');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Event:', message.event, message.data);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from service');
};
```

### Example: Connecting with Python

```python
import asyncio
import websockets
import json

async def connect():
    uri = "ws://localhost:8000/audio"
    async with websockets.connect(uri) as websocket:
        # Receive welcome message
        message = await websocket.recv()
        data = json.loads(message)
        print(f"Connected: {data}")

        # Send audio data (example)
        # audio_bytes = ... your 16-bit PCM audio
        # await websocket.send(audio_bytes)

        # Receive events
        async for message in websocket:
            data = json.loads(message)
            print(f"Event: {data['event']}, Data: {data['data']}")

asyncio.run(connect())
```

## Event Types

The server sends JSON messages with the following structure:

```json
{
  "event": "event_type",
  "data": { ... },
  "timestamp": 1234567890.123
}
```

### Event: `info`

Informational messages, including the welcome message.

**Example:**
```json
{
  "event": "info",
  "data": {
    "message": "Connected to real-time transcription service",
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  },
  "timestamp": 1234567890.123
}
```

### Event: `proper_speech_start`

Sent when VAD confirms proper speech has started (after initial detection).

**Example:**
```json
{
  "event": "proper_speech_start",
  "data": {
    "duration": 0.512
  },
  "timestamp": 1234567890.456
}
```

### Event: `speech_false_detection`

Sent when detected speech was too short (< 1.5s) and discarded.

**Example:**
```json
{
  "event": "speech_false_detection",
  "data": {
    "reason": "utterance_too_short"
  },
  "timestamp": 1234567890.789
}
```

### Event: `speech_end`

Sent when speech segment has ended.

**Example:**
```json
{
  "event": "speech_end",
  "data": {
    "duration": 3.245
  },
  "timestamp": 1234567891.012
}
```

### Event: `transcription`

Sent when transcription is complete (after speech_end).

**Example:**
```json
{
  "event": "transcription",
  "data": {
    "text": "Hello, this is a test transcription.",
    "language": "en",
    "duration": 2.341,
    "segments": [
      {
        "start": 0.0,
        "end": 3.245,
        "text": "Hello, this is a test transcription."
      }
    ]
  },
  "timestamp": 1234567893.456
}
```

### Event: `error`

Sent when an error occurs during processing.

**Example:**
```json
{
  "event": "error",
  "data": {
    "message": "Error processing audio: ..."
  },
  "timestamp": 1234567890.999
}
```

## Sending Audio Data

Send audio as **binary data** (not JSON). The audio should be 16-bit PCM samples.

### Example: Sending from JavaScript (Web Audio API)

```javascript
// Capture audio from microphone
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    const audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(512, 1, 1);

    processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0);
      
      // Convert float32 (-1 to 1) to int16 (-32768 to 32767)
      const int16Data = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        int16Data[i] = Math.max(-32768, Math.min(32767, 
          Math.floor(inputData[i] * 32768)));
      }
      
      // Send binary data
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(int16Data.buffer);
      }
    };

    source.connect(processor);
    processor.connect(audioContext.destination);
  });
```

### Example: Sending from Python

```python
import wave
import asyncio
import websockets

async def send_audio_file(filepath):
    uri = "ws://localhost:8000/audio"
    async with websockets.connect(uri) as websocket:
        # Receive welcome message
        welcome = await websocket.recv()
        print(json.loads(welcome))

        # Open audio file
        with wave.open(filepath, 'rb') as wf:
            # Verify format
            assert wf.getnchannels() == 1  # Mono
            assert wf.getsampwidth() == 2  # 16-bit
            assert wf.getframerate() == 16000  # 16kHz

            # Send in chunks
            chunk_size = 512  # samples
            while True:
                frames = wf.readframes(chunk_size)
                if not frames:
                    break
                
                await websocket.send(frames)
                await asyncio.sleep(0.032)  # 32ms per chunk

        # Receive final events
        try:
            while True:
                message = await asyncio.wait_for(
                    websocket.recv(), timeout=5.0
                )
                data = json.loads(message)
                print(f"Event: {data['event']}")
                if data['event'] == 'transcription':
                    print(f"Text: {data['data']['text']}")
        except asyncio.TimeoutError:
            pass

asyncio.run(send_audio_file('audio.wav'))
```

## Configuration

### Default Configuration

The WebSocket uses these default settings:

```python
VAD Configuration:
  - threshold: 0.5 (speech detection threshold)
  - min_speech_duration_ms: 250
  - min_silence_duration_ms: 100
  - pre_roll_buffer_ms: 300
  - min_utterance_length_s: 1.5

Transcription Configuration:
  - model: large-v3 (WhisperX model)
  - language: auto-detect (or from DEFAULT_LANG env var)
  - device: cuda (if available, else cpu)
  - compute_type: float16 (cuda) or int8 (cpu)
  - batch_size: 16
```

### Customization

Currently, configuration is set server-side via environment variables. Future versions may support per-session configuration via query parameters or initial messages.

## Monitoring

### Active Sessions Endpoint

Get the number of active WebSocket connections:

```bash
curl http://localhost:8000/audio/sessions
```

**Response:**
```json
{
  "active_sessions": 3
}
```

## Best Practices

### 1. Handle Connection Errors

Always implement error handling and reconnection logic:

```javascript
function connect() {
  const ws = new WebSocket('ws://localhost:8000/audio');
  
  ws.onclose = () => {
    console.log('Connection closed, reconnecting...');
    setTimeout(connect, 1000);
  };
  
  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
}
```

### 2. Proper Audio Format

Ensure audio is in the correct format:
- Sample rate: 16 kHz (resample if necessary)
- Bit depth: 16-bit PCM
- Channels: Mono (convert stereo to mono if needed)

### 3. Chunk Size

Use appropriate chunk sizes for smooth streaming:
- Too small: Overhead from many messages
- Too large: Increased latency
- Recommended: 512-2048 samples (32-128ms at 16kHz)

### 4. Event Handling

Implement handlers for all event types:

```javascript
ws.onmessage = (event) => {
  const { event: eventType, data } = JSON.parse(event.data);
  
  switch (eventType) {
    case 'proper_speech_start':
      // Show "listening" indicator
      break;
    case 'speech_end':
      // Show "processing" indicator
      break;
    case 'transcription':
      // Display transcription result
      console.log('Transcription:', data.text);
      break;
    case 'error':
      // Handle error
      console.error('Error:', data.message);
      break;
  }
};
```

### 5. Resource Cleanup

Always clean up resources when done:

```javascript
function cleanup() {
  if (ws) {
    ws.close();
  }
  if (audioContext) {
    audioContext.close();
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(track => track.stop());
  }
}

window.addEventListener('beforeunload', cleanup);
```

## Troubleshooting

### Issue: No Events Received

**Possible causes:**
- Audio format is incorrect (not 16-bit PCM at 16kHz)
- Audio volume too low (VAD not detecting speech)
- Utterances too short (< 1.5s)

**Solutions:**
- Verify audio format matches requirements
- Increase microphone gain
- Speak for longer periods

### Issue: High Latency

**Possible causes:**
- Large chunk sizes
- Network latency
- Server overload

**Solutions:**
- Reduce chunk size (e.g., 512 samples)
- Use faster model (e.g., `tiny` instead of `large-v3`)
- Scale server horizontally

### Issue: Frequent False Detections

**Possible causes:**
- Background noise
- VAD threshold too low

**Solutions:**
- Use noise-canceling microphone
- Process audio in quieter environment
- Adjust VAD threshold (server-side configuration)

## Performance Considerations

### Model Selection

| Model | Speed | Accuracy | GPU Memory | Use Case |
|-------|-------|----------|------------|----------|
| tiny | Fastest | Low | ~1GB | Low-latency, draft transcription |
| base | Fast | Medium | ~1.5GB | Balanced performance |
| small | Moderate | Good | ~2GB | Good accuracy with reasonable speed |
| medium | Slow | Better | ~5GB | High accuracy needed |
| large-v3 | Slowest | Best | ~10GB | Maximum accuracy |

### Concurrency

The server supports multiple concurrent WebSocket connections. Each session:
- Has independent VAD state
- Processes audio independently
- Uses shared model resources (loaded once per worker)

### Resource Usage

- **CPU**: Minimal for VAD, moderate-high for transcription
- **GPU**: High during transcription (if using CUDA)
- **Memory**: ~10GB for large-v3 model, plus audio buffers per session
- **Network**: ~32 KB/s per session at 16kHz 16-bit PCM

## Example Use Cases

### 1. Voice Assistant

```javascript
// Start listening on button press
startButton.onclick = async () => {
  const ws = new WebSocket('ws://localhost:8000/audio');
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  
  // Setup audio processing...
  
  ws.onmessage = (event) => {
    const { event: eventType, data } = JSON.parse(event.data);
    if (eventType === 'transcription') {
      processCommand(data.text);
    }
  };
};
```

### 2. Live Captioning

```javascript
const transcriptDiv = document.getElementById('transcript');

ws.onmessage = (event) => {
  const { event: eventType, data } = JSON.parse(event.data);
  
  if (eventType === 'proper_speech_start') {
    transcriptDiv.innerHTML += '<span class="listening">...</span>';
  } else if (eventType === 'transcription') {
    transcriptDiv.lastChild.textContent = data.text;
  }
};
```

### 3. Meeting Transcription

```python
import asyncio
import websockets
import pyaudio

async def transcribe_meeting():
    uri = "ws://localhost:8000/audio"
    
    # Setup audio capture
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=512
    )
    
    async with websockets.connect(uri) as ws:
        # Receive welcome
        await ws.recv()
        
        # Stream audio
        while True:
            audio_data = stream.read(512)
            await ws.send(audio_data)
            
            # Check for events
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.001)
                data = json.loads(msg)
                if data['event'] == 'transcription':
                    print(f"Speaker: {data['data']['text']}")
            except asyncio.TimeoutError:
                pass

asyncio.run(transcribe_meeting())
```

## References

- [WhisperX GitHub](https://github.com/m-bain/whisperx)
- [Silero-VAD GitHub](https://github.com/snakers4/silero-vad)
- [How to Implement High-Speed Voice Recognition in Chatbot Systems](https://medium.com/@aidenkoh/how-to-implement-high-speed-voice-recognition-in-chatbot-systems-with-whisperx-silero-vad-cdd45ea30904)
