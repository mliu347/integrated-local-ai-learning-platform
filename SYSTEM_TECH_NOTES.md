# System 1 and System 2 Technical Notes

## System 2 turn-taking design

The chatbot should not immediately take the floor after every short pause. In classroom dialogue this is usually described as:

- adaptive turn-taking
- endpointing
- voice activity detection
- barge-in handling
- incremental ASR
- dialogic scaffolding

For second-language learners, a one-second silence threshold is usually too short because students often pause to search for vocabulary. This prototype now uses an adaptive wait window of about 1.45-2.4 seconds for normal student turns, and about 1.05-1.7 seconds after interruption. The opening prompt is designed as student-agency scaffolding: the AI first encourages the student to choose an idea and begin the dialogue.

## System 1 translation and dubbing

The current local pipeline is:

1. Whisper.cpp extracts source-language speech and timestamps.
2. Ollama/Qwen post-edits the rough English translation.
3. A local glossary corrects known classroom terms.
4. Local TTS generates English speech per segment.
5. FFmpeg places the English speech back on the source timeline.

This improves translation quality, but it is not full lip-sync. It is segment-level dubbing alignment.

## Why the lips do not match yet

True mouth-shape synchronization requires an additional lip-sync model. The system would need one of these modules:

- Wav2Lip: classic face-mouth synchronization for a new audio track.
- MuseTalk: modern real-time or near-real-time talking-face synchronization.
- SadTalker / LivePortrait-style pipelines: more suitable for portrait animation than full video scenes.

Without one of these, the system can align English audio to the original time segments, but it cannot change the mouth movement of people already in the video.

## Why Doubao / ChatGPT-style voices sound more emotional

Commercial voice systems usually combine several components:

- large neural TTS models trained on expressive speech
- prosody prediction for pitch, rhythm, stress, and pauses
- emotion or style tokens such as friendly, excited, calm, encouraging
- dialogue-context conditioning so the voice reacts to meaning
- high-quality vocoders
- interruption-aware streaming playback

This proprietary stack cannot be copied directly, but a local research version can approximate it by adding CosyVoice, ChatTTS, F5-TTS, XTTS-v2, or Fish Speech. Piper is fast and local, but it is not as emotionally expressive.

## Topic-to-video generation

The local topic mode is now a scene-synced storyboard video: each visual slide has its own narration clip and subtitle timing. This is still not a generative animation model. To create richer animation, the next technical layer would be:

- image generation for each scene
- motion generation or AnimateDiff-style animation
- visual storyboard planning from the topic script
- audio-driven timing for scene transitions

## Speed limits

Four-to-five-minute uploaded videos take time because the system must run ASR, LLM translation post-editing, TTS, audio alignment, and FFmpeg composition locally. Faster modes are possible:

- fast mode: Whisper translation + glossary only
- quality mode: Whisper + Ollama/Qwen post-edit
- research mode: Whisper + stronger translation model + emotional TTS + lip-sync

The current system defaults toward quality mode because the research requirement prioritizes translation quality over instant output.
