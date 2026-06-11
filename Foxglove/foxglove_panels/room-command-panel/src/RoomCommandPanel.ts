import { PanelExtensionContext } from "@foxglove/extension";

export function initRoomCommandPanel(context: PanelExtensionContext): void {
  const root = context.panelElement;

  // ── Styles & HTML ─────────────────────────────────────────────────────
  root.innerHTML = `
    <style>
      :host, .rc-root {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: #e0e0e0;
      }
      .rc-root {
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 14px;
        height: 100%;
        box-sizing: border-box;
        overflow: auto;
        background: transparent;
      }
      .rc-title {
        margin: 0;
        font-size: 17px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .rc-row {
        display: flex;
        gap: 8px;
        align-items: center;
        flex-wrap: wrap;
      }
      .rc-input {
        flex: 1;
        min-width: 160px;
        padding: 10px 14px;
        border: 1px solid #555;
        border-radius: 8px;
        font-size: 14px;
        outline: none;
        background: #2a2a2a;
        color: #e0e0e0;
        transition: border-color 0.2s;
      }
      .rc-input:focus { border-color: #5b9bd5; }
      .rc-input::placeholder { color: #888; }
      .rc-btn {
        padding: 10px 20px;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        background: #5b9bd5;
        color: white;
        transition: background 0.15s;
      }
      .rc-btn:hover { background: #4a8ac4; }
      .rc-btn:active { background: #3a7ab4; }
      .rc-mic {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        border: 2px solid #555;
        cursor: pointer;
        font-size: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #2a2a2a;
        transition: all 0.2s;
        flex-shrink: 0;
      }
      .rc-mic:hover { border-color: #5b9bd5; background: #333; }
      .rc-mic.listening {
        background: #c0392b;
        border-color: #e74c3c;
        animation: rc-pulse 1.2s ease-in-out infinite;
      }
      @keyframes rc-pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.4); }
        50%      { box-shadow: 0 0 0 10px rgba(231, 76, 60, 0); }
      }
      .rc-lang {
        padding: 8px 10px;
        border: 1px solid #555;
        border-radius: 8px;
        font-size: 13px;
        background: #2a2a2a;
        color: #e0e0e0;
        cursor: pointer;
      }
      .rc-transcript {
        flex: 1;
        min-width: 100px;
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 13px;
        background: #252525;
        color: #999;
        font-style: italic;
        min-height: 20px;
      }
      .rc-feedback {
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 13px;
        background: #1a2a3a;
        border-left: 4px solid #5b9bd5;
        white-space: pre-wrap;
        line-height: 1.4;
      }
      .rc-feedback.error {
        border-left-color: #e74c3c;
        background: #2a1a1a;
      }
      .rc-feedback.success {
        border-left-color: #27ae60;
        background: #1a2a1a;
      }
      .rc-divider {
        height: 1px;
        background: #333;
        margin: 2px 0;
      }
      .rc-hint {
        font-size: 12px;
        color: #666;
        line-height: 1.5;
      }
    </style>

    <div class="rc-root">
      <h3 class="rc-title">🏥 Room Navigator</h3>

      <div class="rc-row">
        <input id="rc-cmd" class="rc-input" type="text"
               placeholder="e.g. &quot;Go to urgences&quot; / &quot;Aller à la salle 101&quot;" />
        <button id="rc-send" class="rc-btn">Send</button>
      </div>

      <div class="rc-row">
        <button id="rc-mic" class="rc-mic" title="Hold to speak">🎤</button>
        <select id="rc-lang" class="rc-lang">
          <option value="fr-FR">🇫🇷 Français</option>
          <option value="en-US">🇬🇧 English</option>
        </select>
        <span id="rc-transcript" class="rc-transcript"></span>
      </div>

      <div id="rc-feedback" class="rc-feedback" style="display:none;"></div>

      <div class="rc-divider"></div>
      <div class="rc-hint">
        Type a room name or speak a command. Examples:<br/>
        • "Go to urgences" &nbsp; • "Salle 101" &nbsp; • "Navigate to room 204"
      </div>
    </div>
  `;

  // ── Element references ────────────────────────────────────────────────
  const cmdInput    = root.querySelector("#rc-cmd")       as HTMLInputElement;
  const sendBtn     = root.querySelector("#rc-send")      as HTMLButtonElement;
  const micBtn      = root.querySelector("#rc-mic")       as HTMLButtonElement;
  const langSelect  = root.querySelector("#rc-lang")      as HTMLSelectElement;
  const transcriptEl = root.querySelector("#rc-transcript") as HTMLElement;
  const feedbackEl  = root.querySelector("#rc-feedback")  as HTMLElement;

  // ── Advertise /room_command for publishing ────────────────────────────
  try {
    context.advertise?.("/room_command", "std_msgs/msg/String", {
      datatypes: new Map([
        [
          "std_msgs/msg/String",
          { definitions: [{ name: "data", type: "string", isComplex: false }] },
        ],
      ]),
    });
  } catch {
    console.warn("Could not advertise /room_command — publishing may not work");
  }

  // ── Subscribe to /room_command_feedback ───────────────────────────────
  context.subscribe([{ topic: "/room_command_feedback" }]);

  context.onRender = (renderState, done) => {
    if (renderState.currentFrame) {
      for (const msg of renderState.currentFrame) {
        if (msg.topic === "/room_command_feedback") {
          const text = (msg.message as { data: string }).data;
          feedbackEl.textContent = text;
          feedbackEl.style.display = "block";

          const isError = text.toLowerCase().includes("not found");
          const isNav   = text.toLowerCase().includes("navigating");
          feedbackEl.className = "rc-feedback"
            + (isError ? " error" : "")
            + (isNav   ? " success" : "");
        }
      }
    }
    done();
  };
  context.watch("currentFrame");

  // ── Send command ──────────────────────────────────────────────────────
  function sendCommand(text: string): void {
    text = text.trim();
    if (!text) return;

    try {
      context.publish?.("/room_command", { data: text });
      transcriptEl.textContent = `Sent: "${text}"`;
      cmdInput.value = "";
    } catch (err) {
      transcriptEl.textContent = `Publish error: ${err}`;
    }
  }

  sendBtn.addEventListener("click", () => sendCommand(cmdInput.value));
  cmdInput.addEventListener("keydown", (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendCommand(cmdInput.value);
    }
  });

  // ── Voice input (Web Speech API) ──────────────────────────────────────
  let recognition: any = null;

  micBtn.addEventListener("click", () => {
    // If already listening, stop
    if (recognition) {
      recognition.stop();
      return;
    }

    const SR =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SR) {
      transcriptEl.textContent =
        "⚠ Speech recognition not available — use text input instead";
      return;
    }

    recognition = new SR();
    recognition.lang = langSelect.value;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    recognition.onstart = () => {
      micBtn.classList.add("listening");
      transcriptEl.textContent = "🔴 Listening…";
    };

    recognition.onresult = (event: any) => {
      const result = event.results[event.results.length - 1];
      const text: string = result[0].transcript;

      if (result.isFinal) {
        transcriptEl.textContent = `"${text}"`;
        sendCommand(text);
      } else {
        transcriptEl.textContent = `"${text}" …`;
      }
    };

    recognition.onend = () => {
      micBtn.classList.remove("listening");
      recognition = null;
    };

    recognition.onerror = (event: any) => {
      const msg =
        event.error === "not-allowed"
          ? "Microphone access denied — check browser permissions"
          : event.error === "no-speech"
            ? "No speech detected — try again"
            : `Speech error: ${event.error}`;
      transcriptEl.textContent = `⚠ ${msg}`;
      micBtn.classList.remove("listening");
      recognition = null;
    };

    recognition.start();
  });
}