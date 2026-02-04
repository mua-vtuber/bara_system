# Voice Subsystem Documentation

## Overview

The Voice Subsystem enables real-time voice command processing through wake word detection and speech-to-text (STT) transcription. All voice components are **optional dependencies** and the system gracefully degrades if they are not installed.

## Architecture

### Components

1. **WakeWordEngine** (`app/voice/wake_word.py`)
   - Detects wake words in audio stream
   - Supports multiple backends: OpenWakeWord, Porcupine
   - Graceful fallback if dependencies not installed

2. **WhisperEngine** (`app/voice/whisper.py`)
   - Converts speech to text using OpenAI Whisper
   - VRAM-aware: loads model on-demand, unloads after use
   - Supports multiple model sizes: tiny, base, small, medium, large

3. **VoiceService** (`app/services/voice.py`)
   - Orchestrates wake word detection and STT pipeline
   - State machine: IDLE → LISTENING → TRANSCRIBING → IDLE
   - Emits `VoiceCommandEvent` when transcription completes

4. **WebSocket Audio Endpoint** (`app/api/websocket/audio.py`)
   - Real-time audio streaming: `/ws/audio`
   - Binary protocol for PCM audio data
   - JSON control messages for session management

## Configuration

In `config.json`:

```json
{
  "voice": {
    "enabled": false,
    "wake_word_engine": "openwakeword",
    "stt_model": "base",
    "language": "ko",
    "audio_source": "browser"
  },
  "bot": {
    "wake_words": ["hey assistant", "computer"]
  }
}
```

### Voice Configuration Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Enable/disable voice subsystem |
| `wake_word_engine` | str | `"openwakeword"` | Wake word engine: `"openwakeword"` or `"porcupine"` |
| `stt_model` | str | `"base"` | Whisper model: `"tiny"`, `"base"`, `"small"`, `"medium"`, `"large"` |
| `language` | str | `"ko"` | Language code for STT (e.g., `"ko"`, `"en"`, `"auto"`) |
| `audio_source` | str | `"browser"` | Audio source identifier (for future use) |

### Bot Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `wake_words` | list[str] | `[]` | List of wake words to detect |

## Optional Dependencies

Voice subsystem requires additional packages. Install with:

```bash
# Core voice dependencies
pip install openai-whisper torch numpy soundfile

# Wake word detection (choose one)
pip install openwakeword  # Open-source, recommended
pip install pvporcupine  # Commercial, requires license key
```

### Dependency Matrix

| Feature | Required Packages | Notes |
|---------|------------------|-------|
| Speech-to-text | `openai-whisper`, `torch`, `numpy` | Torch enables GPU acceleration |
| Audio decoding | `soundfile` | Supports WAV, MP3, etc. |
| Wake word (OpenWakeWord) | `openwakeword` | Open-source, CPU-efficient |
| Wake word (Porcupine) | `pvporcupine` | Commercial, requires API key |

## VRAM Management

The Whisper model can consume significant VRAM (500MB - 3GB depending on model size). The subsystem implements automatic VRAM management:

1. **On-demand loading**: Model loads only when transcription is needed
2. **Immediate unload**: Model unloads after each transcription
3. **Cache clearing**: CUDA cache is cleared on unload

### Model Sizes and VRAM Usage

| Model | VRAM (approx) | Speed | Accuracy |
|-------|---------------|-------|----------|
| tiny | ~400 MB | Very Fast | Low |
| base | ~500 MB | Fast | Good |
| small | ~1 GB | Medium | Better |
| medium | ~2 GB | Slow | Very Good |
| large | ~3 GB | Very Slow | Best |

## WebSocket Protocol

### Connection

```
WS ws://localhost:8000/ws/audio?token=<session_token>
```

Authentication required via query parameter `token`.

### Client → Server Messages

**Binary frames**: Raw PCM audio data
- Format: 16kHz, 16-bit, mono PCM
- Chunk size: Typically 1024-4096 bytes

**JSON control messages**:

```json
{"type": "start"}   // Start listening session (optional)
{"type": "stop"}    // Stop and finalize transcription
{"type": "status"}  // Request current status
{"type": "ping"}    // Keep-alive
```

### Server → Client Messages

```json
// Wake word detected, now collecting audio
{"type": "wake_word_detected"}

// Transcription result
{"type": "transcript", "text": "안녕하세요"}

// Current listening state
{"type": "status", "listening": false}

// Keep-alive response
{"type": "pong"}

// Error occurred
{"type": "error", "message": "..."}
```

## State Machine

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  ┌──────┐  wake_word   ┌───────────┐  silence  │
│  │ IDLE ├─────────────▶│ LISTENING ├───────────┤
│  └──────┘              └─────┬─────┘           │
│     ▲                        │                 │
│     │                        │ finalize        │
│     │                        ▼                 │
│     │                  ┌──────────┐            │
│     └──────────────────┤TRANSCRIBE│            │
│        transcribe      └──────────┘            │
│        + emit event                            │
└─────────────────────────────────────────────────┘
```

1. **IDLE**: Waiting for wake word in incoming audio
2. **LISTENING**: Wake word detected, collecting audio for STT
3. **TRANSCRIBING**: Processing collected audio with Whisper
4. Back to **IDLE**: Transcription complete, model unloaded

## Events

### VoiceCommandEvent

Emitted when transcription completes successfully.

```python
@dataclass(frozen=True)
class VoiceCommandEvent(Event):
    transcript: str = ""
    confidence: float = 0.0
```

Subscribe to voice commands:

```python
async def handle_voice_command(event: VoiceCommandEvent):
    print(f"User said: {event.transcript}")

await event_bus.subscribe(VoiceCommandEvent, handle_voice_command)
```

## Error Handling

### Graceful Degradation

If voice dependencies are not installed:
1. VoiceService sets `_enabled = False`
2. WebSocket endpoint returns 4503 (Service Unavailable)
3. System logs warnings but continues normal operation

### Import Protection

All voice imports are wrapped in try/except:

```python
try:
    import whisper
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False
```

### Runtime Errors

- Wake word detection failures: Logged, returns `False`
- Transcription failures: Logged, returns `None`, resets state
- WebSocket errors: Client receives `{"type": "error", "message": "..."}`

## Usage Examples

### Enable Voice in Config

```json
{
  "voice": {
    "enabled": true,
    "wake_word_engine": "openwakeword",
    "stt_model": "base",
    "language": "ko"
  },
  "bot": {
    "wake_words": ["안녕", "컴퓨터"]
  }
}
```

### WebSocket Client (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/audio?token=' + sessionToken);

// Handle text messages (JSON)
ws.onmessage = (event) => {
  if (typeof event.data === 'string') {
    const msg = JSON.parse(event.data);

    if (msg.type === 'wake_word_detected') {
      console.log('Wake word detected! Listening...');
    } else if (msg.type === 'transcript') {
      console.log('You said:', msg.text);
    } else if (msg.type === 'status') {
      console.log('Listening:', msg.listening);
    }
  }
};

// Stream microphone audio
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    const audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (e) => {
      const pcmData = e.inputBuffer.getChannelData(0);
      // Convert Float32Array to Int16Array
      const int16 = new Int16Array(pcmData.length);
      for (let i = 0; i < pcmData.length; i++) {
        int16[i] = Math.max(-32768, Math.min(32767, pcmData[i] * 32768));
      }
      ws.send(int16.buffer);
    };

    source.connect(processor);
    processor.connect(audioContext.destination);
  });

// Manually stop listening
function stopListening() {
  ws.send(JSON.stringify({ type: 'stop' }));
}
```

### Subscribe to Voice Commands

```python
from app.models.events import VoiceCommandEvent

async def on_voice_command(event: VoiceCommandEvent):
    """Handle voice command transcription."""
    logger.info(f"Voice command: {event.transcript} (confidence: {event.confidence})")

    # Process command with LLM or command parser
    response = await process_command(event.transcript)
    # ...

# In lifespan startup:
await event_bus.subscribe(VoiceCommandEvent, on_voice_command)
```

## Testing

### Without Dependencies

System should start normally with voice disabled:

```bash
python -m app.main
# Logs: "Voice service disabled or unavailable"
```

### With Dependencies

```bash
pip install openai-whisper torch numpy soundfile openwakeword

# Update config.json
{
  "voice": { "enabled": true },
  "bot": { "wake_words": ["hey bot"] }
}

python -m app.main
# Logs: "Voice service started"
# Logs: "OpenWakeWord engine initialized with words: ['hey bot']"
```

### Manual Audio Processing

```python
import asyncio
from app.services.voice import VoiceService
from app.core.config import Config
from app.core.events import EventBus

async def test_voice():
    config = Config.from_file()
    event_bus = EventBus()
    voice = VoiceService(config, event_bus)

    await voice.start()

    # Simulate audio chunks
    with open('test_audio.pcm', 'rb') as f:
        while chunk := f.read(4096):
            result = await voice.process_audio(chunk)
            if result:
                print(f"Transcription: {result}")

    await voice.stop()

asyncio.run(test_voice())
```

## Performance Considerations

### CPU vs GPU

- **CPU**: Whisper works on CPU but is significantly slower (5-10x)
- **GPU**: Requires CUDA-compatible GPU and `torch` with CUDA support
- Install GPU-enabled PyTorch: `pip install torch --index-url https://download.pytorch.org/whl/cu118`

### Latency

Typical latency (base model, GPU):
1. Wake word detection: <100ms
2. Audio collection: 2-5 seconds (user speech)
3. Transcription: 1-3 seconds
4. Total: 3-8 seconds from wake word to transcript

### Optimization Tips

1. **Use smaller models**: `tiny` or `base` for real-time feel
2. **GPU acceleration**: Essential for production use
3. **Voice Activity Detection (VAD)**: Better than silence detection
4. **Model caching**: Keep model loaded if commands are frequent

## Security

### Authentication

- All WebSocket connections require valid session token
- Token passed as query parameter: `?token=<session_token>`
- Invalid tokens result in immediate connection close (4401)

### Privacy

- Audio is processed locally, not sent to external APIs
- No audio recording/storage unless explicitly implemented
- Transcripts are logged but not persisted by default

### Rate Limiting

Consider adding rate limits to prevent abuse:
- Max concurrent audio connections per user
- Max transcription requests per minute
- Max audio data size per session

## Troubleshooting

### Voice service won't start

**Symptom**: `Voice service disabled or unavailable`

**Solutions**:
1. Check `config.json`: `voice.enabled` must be `true`
2. Install dependencies: `pip install openai-whisper torch numpy`
3. Check logs for ImportError details

### CUDA out of memory

**Symptom**: `RuntimeError: CUDA out of memory`

**Solutions**:
1. Use smaller model: Change `stt_model` to `"tiny"` or `"base"`
2. Ensure model unloading: Check `WhisperEngine.unload_model()` is called
3. Close other GPU-intensive applications
4. Use CPU mode: Set `CUDA_VISIBLE_DEVICES=""` environment variable

### Wake word not detected

**Symptom**: No `wake_word_detected` messages

**Solutions**:
1. Check `bot.wake_words` in config
2. Ensure audio format is correct (16kHz, 16-bit, mono)
3. Check microphone volume/gain
4. Try different wake words (some work better than others)
5. Test with OpenWakeWord's demo app first

### Poor transcription quality

**Symptom**: Incorrect or garbled transcriptions

**Solutions**:
1. Use larger model: `"small"` or `"medium"` instead of `"base"`
2. Ensure correct language code: Set `voice.language` to match spoken language
3. Improve audio quality: Use better microphone, reduce background noise
4. Check sample rate: Must be 16kHz for Whisper

## Future Enhancements

- [ ] Voice Activity Detection (VAD) for better silence detection
- [ ] Support for multiple languages in single session
- [ ] Custom wake word training
- [ ] Audio recording/playback for debugging
- [ ] Real-time partial transcriptions (streaming STT)
- [ ] Speaker diarization (identify multiple speakers)
- [ ] Integration with TTS for voice responses
