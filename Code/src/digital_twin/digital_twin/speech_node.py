#!/usr/bin/env python3
"""
speech_node.py — Voice-to-ROS2 bridge for room commands.

Subscribes:
    /speech_trigger  (std_msgs/String)  — language code ("fr" or "en") to start

Publishes:
    /room_command    (std_msgs/String)  — transcribed text → room_interpreter
    /speech_status   (std_msgs/String)  — UI state for the Foxglove panel
        Values: "ready", "recording", "transcribing", "heard:<text>",
                "no_speech", "error:<msg>"

Requires:
    pip install faster-whisper sounddevice numpy --break-system-packages
"""

import signal
import sys
import threading

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class SpeechNode(Node):

    def __init__(self):
        super().__init__('speech_node')

        # ── Parameters ──────────────────────────────────────────────────
        self.declare_parameter('model_size', 'base')       # tiny, base, small, medium
        self.declare_parameter('default_language', 'en')    # fallback language
        self.declare_parameter('sample_rate', 16000)
        self.declare_parameter('max_duration', 8.0)         # seconds
        self.declare_parameter('silence_threshold', 0.01)   # RMS below = silence
        self.declare_parameter('silence_duration', 1.5)     # seconds of silence to stop
        self.declare_parameter('device_index', -1)  # -1 = system default
        
        self.device_idx = self.get_parameter('device_index').value
        self.model_size = self.get_parameter('model_size').value
        self.default_lang = self.get_parameter('default_language').value
        self.sample_rate = self.get_parameter('sample_rate').value
        self.max_dur = self.get_parameter('max_duration').value
        self.sil_thr = self.get_parameter('silence_threshold').value
        self.sil_dur = self.get_parameter('silence_duration').value

        self.recording = False

        # ── Load Whisper (deferred import — heavy) ──────────────────────
        self.get_logger().info(f'Loading Whisper model "{self.model_size}" …')
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(self.model_size, compute_type='int8')
            self.get_logger().info('Whisper model loaded ✓')
        except ImportError:
            self.get_logger().error(
                'faster-whisper not installed. Run:\n'
                '  pip install faster-whisper sounddevice numpy --break-system-packages')
            raise

        # ── ROS interfaces ──────────────────────────────────────────────
        self.create_subscription(
            String, '/speech_trigger', self._on_trigger, 10)

        self.cmd_pub    = self.create_publisher(String, '/room_command', 10)
        self.status_pub = self.create_publisher(String, '/speech_status', 10)

        self._set_status('ready')
        self.get_logger().info('SpeechNode ready — waiting for trigger on /speech_trigger')

    # ═══════════════════════════ Helpers ════════════════════════════════

    def _set_status(self, text: str):
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)

    # ═══════════════════════════ Trigger ════════════════════════════════

    def _on_trigger(self, msg: String):
        if self.recording:
            self.get_logger().warn('Already recording — ignoring trigger')
            return

        lang = msg.data.strip() if msg.data.strip() else self.default_lang
        self.get_logger().info(f'Trigger received — language="{lang}"')

        thread = threading.Thread(target=self._record_and_transcribe,
                                  args=(lang,), daemon=True)
        thread.start()

    # ═══════════════════════════ Pipeline ═══════════════════════════════

    def _record_and_transcribe(self, lang: str):
        import sounddevice as sd          # imported here so node starts fast

        self.recording = True
        self._set_status('recording')
        self.get_logger().info('🎙  Recording …')

        try:
            # ── Record ──────────────────────────────────────────────────
            audio = self._capture(sd)

            if audio is None or len(audio) < self.sample_rate * 0.3:
                self._set_status('no_speech')
                self.get_logger().info('No speech detected')
                return

            # ── Transcribe ──────────────────────────────────────────────
            self._set_status('transcribing')
            self.get_logger().info('Transcribing …')

            segments, _ = self.model.transcribe(
                audio,
                language=lang,
                beam_size=5,
                vad_filter=True,
            )
            text = ' '.join(s.text.strip() for s in segments).strip()

            if text:
                self.get_logger().info(f'Transcribed: "{text}"')
                self._set_status(f'heard:{text}')

                cmd = String()
                cmd.data = text
                self.cmd_pub.publish(cmd)
            else:
                self._set_status('no_speech')
                self.get_logger().info('Empty transcription')

        except Exception as e:
            self.get_logger().error(f'Speech error: {e}')
            self._set_status(f'error:{e}')

        finally:
            self.recording = False
            # Small delay so the panel sees "heard:…" before "ready"
            import time
            time.sleep(2.0)
            self._set_status('ready')

    def _capture(self, sd):
        """Record from default mic until silence or max duration."""
        chunk_dur   = 0.1                                     # 100 ms
        chunk_size  = int(self.sample_rate * chunk_dur)
        max_chunks  = int(self.max_dur / chunk_dur)
        sil_chunks  = int(self.sil_dur / chunk_dur)

        audio_chunks = []
        silent_count = 0

        device = self.device_idx if self.device_idx >= 0 else None

        with sd.InputStream(samplerate=self.sample_rate,
                            channels=1, dtype='float32',
                            device=device) as stream:
            for i in range(max_chunks):
                chunk, _ = stream.read(chunk_size)
                audio_chunks.append(chunk.copy())

                rms = float(np.sqrt(np.mean(chunk ** 2)))
                if rms < self.sil_thr:
                    silent_count += 1
                else:
                    silent_count = 0

                # Stop after silence, but only if we captured some speech
                if silent_count >= sil_chunks and len(audio_chunks) > sil_chunks + 5:
                    self.get_logger().info(
                        f'Silence detected after {(i+1)*chunk_dur:.1f}s')
                    break

        if not audio_chunks:
            return None

        return np.concatenate(audio_chunks, axis=0).flatten()


# ═══════════════════════════════ Entry ══════════════════════════════════

def main(args=None):
    rclpy.init(args=args)
    node = SpeechNode()

    def _shutdown(sig, frame):
        node.get_logger().info('Shutting down SpeechNode')
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        rclpy.spin(node)
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()