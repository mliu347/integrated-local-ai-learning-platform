Locally Hosted AI-Supported Multimodal English Learning and Research Governance Platform

Overview

English Title:

A Locally Hosted AI-Supported Multimodal English Learning and Research Governance Platform

This platform integrates the previous System 1, System 2, and System 3 into a unified architecture. Rather than functioning as three separate systems, they now operate as interconnected modules within a single platform:

* AI Content Adaptation Module (System 1)
* Student Learning Interface
* Teacher Governance Dashboard
* Research Data Governance Layer

⸻

Running the Platform

cd /Users/xiaojiudechaojizhandouji/Documents/Codex/2026-06-08/new-chat/outputs/integrated-local-ai-learning-platform
./run.sh

Access the platform through:

Student Interface

http://127.0.0.1:8790/student

Teacher Interface

http://127.0.0.1:8790/teacher

Default teacher accounts:

Username	Password
teacher	teacher-demo
researcher	researcher-demo

⸻

System Architecture

AI Content Adaptation Module (System 1)

Teachers or students can:

* Upload local videos
* Enter a video topic
* Generate English learning materials automatically

The module produces:

* English learning videos
* Narration audio
* Subtitles
* Learning scripts
* CEFR-adapted versions (A1/A2/B1)

⸻

Student Learning Interface

Students can:

* Watch generated learning videos
* Upload local videos
* Enter dialogue tasks
* Start or stop the AI voice chatbot
* Participate in spoken or text-based English conversations

The learning experience combines multimodal content consumption with AI-supported dialogic interaction.

⸻

Teacher Governance Dashboard

Teachers and researchers can:

* Monitor student sessions in real time
* Access dialogue histories
* Intervene when necessary
* Add annotations and notes
* Conduct auditing and governance activities
* Export research datasets

⸻

Improvements Implemented

1. Browser-Compatible Video Playback

The previous playback issue in System 1 has been resolved.

Generated videos now use:

* H.264 video encoding
* AAC audio encoding
* yuv420p pixel format
* +faststart optimization
* External VTT subtitles

Videos are served through:

/media/.../learning_video.mp4

and can be played directly using the HTML5 <video> component.

⸻

2. Real-Time Voice Dialogue (System 2)

The student interface now provides explicit chatbot controls.

Start Chatbot

When students click Start Chatbot:

* A student session is created
* Browser speech recognition is activated
* AI responses are generated and spoken aloud

Stop Chatbot

When students click Stop Chatbot:

* Speech recognition stops
* Speech synthesis stops
* The backend records chatbot_listening = false

The chatbot will no longer listen or speak until restarted.

Browser Compatibility

If Web Speech API is unavailable:

* Students can continue using text-based interaction

Additional interface features include:

* Microphone testing
* Real-time speech transcription
* AI voice style indicators

To prevent self-recognition:

* Speech recognition pauses while the AI is speaking
* Recognition automatically resumes after AI speech ends

⸻

2.1 Student-Side Video Adaptation Workflow

Students can now:

Upload Local Videos

Supported formats:

* MP4
* M4V
* MOV
* WebM

Current local deployment supports videos up to approximately five minutes.

Enter a Video Topic

Students may alternatively provide a topic without uploading a video.

Optional Transcript Support

If local Whisper transcription is unavailable, students can manually provide:

* Video notes
* Existing transcripts

Adaptation Process

The system prioritizes adaptation from the original uploaded video.

Rather than generating content solely from a topic template, it attempts to:

* Transcribe the source video
* Interpret supplied notes
* Generate an English learning version based on original content

Outputs include:

* English learning scripts
* CEFR-level adaptations (A1/A2/B1)
* Narration audio
* VTT subtitles
* Browser-compatible MP4 videos

When a local video is uploaded:

* Original video footage is preserved
* Newly generated English narration is added
* English subtitles are overlaid

Students then watch the adapted version and proceed to dialogue practice using System 2.

Continuous Voice Interaction

Once activated:

1. Student speaks
2. AI responds
3. AI finishes speaking
4. Listening automatically resumes

This creates a continuous conversational loop.

⸻

3. Separate Student and Teacher Interfaces

Student Interface

/student

Displays:

* Learning videos
* Chatbot interaction tools
* Dialogue activities

Teacher Interface

/teacher

Displays:

* Governance tools
* Monitoring functions
* Research dashboards

Student and teacher experiences are fully separated.

⸻

4. Student Access to Learning Videos

Students can directly access learning materials generated through System 1.

Displayed content includes:

* Video player
* Subtitle tracks
* Learning topics
* Vocabulary keywords
* Dialogue activities
* Chatbot interaction area

⸻

5. Teacher Governance Dashboard (System 3)

The teacher dashboard includes:

Research Monitoring Overview

* Active student sessions
* Participation summaries
* Learning analytics

Student Dialogue Retrieval

* Search dialogue histories
* Review interaction records

Student Research Profiles

* Individual learner analytics
* Longitudinal participation records

Real-Time Session Monitoring

Including:

* Turn count
* Participation indicators
* Reasoning indicators
* Average English language ratio
* Speech vs. typed interaction counts
* Uploaded video metadata
* Assigned dialogue tasks

Governance Functions

* Safeguarding flags
* Pause session
* Resume session
* Terminate session

Transparency and Accountability

* Live transcript viewing
* Explainability audit records
* Teacher annotations
* Full session retrieval

Research Data Export

* Anonymized dataset generation
* Export-ready research records

⸻

6. Integrated Platform Architecture

The three previous systems now operate as a single connected platform:

AI Content Adaptation Module
            ↓
Student Learning Interface
            ↓
AI Dialogic Interaction Module
            ↓
Teacher Governance Dashboard
            ↓
Research Data Governance Layer

All modules share:

* One backend service
* One data infrastructure
* One governance framework

⸻

Current Implementation Boundaries

Speech Recognition

Voice interaction currently depends on the browser’s Web Speech API.

Support may vary across:

* Browsers
* School devices
* Operating systems

Dialogue Engine

The current chatbot uses a locally hosted rule-based Tech-SEDA dialogic engine.

Future versions may integrate:

* Qwen
* Ollama
* Other locally deployed large language models

Video Generation

Generated learning videos are locally produced and browser-compatible.

Subtitles are provided through VTT tracks.

Access Control

Current authentication uses demonstration passcodes.

Formal educational and research deployments should implement:

* Institutional authentication
* User management
* Audit signatures

Research Data Storage

Although exported datasets are anonymized, formal research deployments should additionally employ:

* Institutionally approved encrypted storage
* Secure research data governance procedures
* Ethics-compliant data management frameworks
