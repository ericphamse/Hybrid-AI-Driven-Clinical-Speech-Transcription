# main.py
import json, time, threading, queue, uuid
from datetime import datetime
from urllib.parse import urlencode

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.utils import platform

import boto3, botocore.auth, botocore.awsrequest
import websocket  # <-- for tracing (optional)
from websocket import create_connection, WebSocketConnectionClosedException
import binascii
import struct

# Optional: see handshake / close codes in your console
# Comment out if too chatty.
websocket.enableTrace(True)

SAMPLE_RATE = 16000
BYTES_PER_CHUNK = 3200       # ~100ms at 16k mono 16-bit
REGION = "ap-southeast-2"
LANG = "en-US"
SPECIALTY = "PRIMARYCARE"
TYPE = "DICTATION"           # or "CONVERSATION"

# ---------- AWS signing ----------
def presign_medical_ws():
    # Build endpoint pieces
    host_no_port = f"transcribestreaming.{REGION}.amazonaws.com"
    host_with_port = f"{host_no_port}:8443"
    path = "/medical-stream-transcription-websocket"

    # Required query params
    query = {
        "language-code": LANG,
        "media-encoding": "pcm",
        "sample-rate": str(SAMPLE_RATE),
        "specialty": SPECIALTY,
        "type": TYPE,
        "session-id": str(uuid.uuid4()),  # Use UUID format for session ID
    }

    # Credentials / signer
    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()

    # Sign ONLY the Host header, and sign it WITH the port (8443)
    req = botocore.awsrequest.AWSRequest(
        method="GET",
        url=f"https://{host_with_port}{path}?{urlencode(query)}",
        headers={"host": host_with_port},
    )
    signer = botocore.auth.SigV4QueryAuth(
        credentials=creds, service_name="transcribe", region_name=REGION, expires=300
    )
    signer.add_auth(req)

    # Return a proper wss:// URL string
    return req.url.replace("https://", "wss://", 1)


# ---------- AWS EventStream helpers ----------
HEADER_TYPE_STRING = 7

def _encode_header(name: str, value: str) -> bytes:
    name_b = name.encode("ascii")
    val_b = value.encode("utf-8")
    return bytes([
        len(name_b)
    ]) + name_b + bytes([HEADER_TYPE_STRING]) + struct.pack(
        ">H", len(val_b)
    ) + val_b

def build_eventstream_message(headers: dict, payload: bytes) -> bytes:
    hdr_bytes = b"".join(_encode_header(k, v) for k, v in headers.items())
    headers_len = len(hdr_bytes)
    total_len = 4 + 4 + 4 + headers_len + len(payload) + 4
    prelude = struct.pack(">II", total_len, headers_len)
    prelude_crc = struct.pack(">I", binascii.crc32(prelude) & 0xFFFFFFFF)
    msg_wo_crc = prelude + prelude_crc + hdr_bytes + payload
    message_crc = struct.pack(">I", binascii.crc32(msg_wo_crc) & 0xFFFFFFFF)
    return msg_wo_crc + message_crc

def parse_eventstream_message(data: bytes):
    if len(data) < 16:
        return None, None
    total_len, headers_len = struct.unpack(">II", data[:8])
    # Skip prelude CRC (already verified by service). We won't verify here.
    pos = 12
    headers = {}
    end_headers = pos + headers_len
    try:
        while pos < end_headers:
            name_len = data[pos]
            pos += 1
            name = data[pos:pos+name_len].decode("ascii")
            pos += name_len
            htype = data[pos]
            pos += 1
            if htype == HEADER_TYPE_STRING:
                slen = struct.unpack(">H", data[pos:pos+2])[0]
                pos += 2
                sval = data[pos:pos+slen].decode("utf-8")
                pos += slen
                headers[name] = sval
            else:
                # Unsupported type; abort
                return None, None
        payload = data[end_headers: total_len - 4]
        return headers, payload
    except Exception:
        return None, None

# ---------- Audio capture (Android / Desktop) ----------
class MicSource:
    """Cross-platform PCM16/16k mono byte producer → puts into a queue."""
    def __init__(self, out_q):
        self.out_q = out_q
        self._running = False
        self._t = None
        self._desktop_stream = None

    def start(self):
        if self._running:
            return
        self._running = True
        
        # Choose audio capture method based on platform
        if platform == "android":
            self._t = threading.Thread(target=self._android_loop, daemon=True)
        else:
            self._t = threading.Thread(target=self._desktop_loop, daemon=True)
        
        self._t.start()

    def stop(self):
        self._running = False
        if self._t:
            self._t.join(timeout=1.0)
            self._t = None

    # --- Android mic via AudioRecord ---
    def _android_loop(self):
        from jnius import autoclass, jarray
        AudioRecord = autoclass('android.media.AudioRecord')
        MediaRecorder = autoclass('android.media.MediaRecorder')
        AudioFormat = autoclass('android.media.AudioFormat')

        buf_size = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        if buf_size < BYTES_PER_CHUNK:
            buf_size = BYTES_PER_CHUNK

        recorder = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            buf_size
        )
        buf = jarray('b', BYTES_PER_CHUNK)
        recorder.startRecording()
        try:
            while self._running:
                read = recorder.read(buf, 0, BYTES_PER_CHUNK)
                if read > 0:
                    self.out_q.put(bytes(buf[:read]))
                else:
                    time.sleep(0.005)
        finally:
            recorder.stop()
            recorder.release()

    # --- Desktop mic via sounddevice ---
    def _desktop_loop(self):
        import sounddevice as sd
        def cb(indata, frames, time_info, status):
            if not self._running:
                raise sd.CallbackAbort
            self.out_q.put(indata.copy().astype('int16').tobytes())
        with sd.InputStream(
            channels=1, samplerate=SAMPLE_RATE, dtype='int16',
            blocksize=BYTES_PER_CHUNK // 2,  # samples (2 bytes/sample)
            callback=cb
        ):
            while self._running:
                time.sleep(0.05)

# ---------- Streaming client ----------
class TranscribeStreamer:
    def __init__(self, ui_log, ui_partial, ui_final):
        self.ui_log = ui_log
        self.ui_partial = ui_partial
        self.ui_final = ui_final
        self.ws = None
        self.audio_q = queue.Queue(maxsize=50)
        self.mic = MicSource(self.audio_q)
        self._send_t = None
        self._recv_t = None
        self._running = False
        self._eos_sent = False

    def log(self, msg):
        def _append(_dt):
            self.ui_log.text += msg + "\n"
            self.ui_log.cursor = (len(self.ui_log.text), 0)
        Clock.schedule_once(_append)

    def set_partial(self, text):
        Clock.schedule_once(lambda _dt: setattr(self.ui_partial, 'text', text))

    def append_final(self, text):
        def _append(_dt):
            self.ui_final.text += (text + " ")
        Clock.schedule_once(_append)

    def start(self):
        if self._running:
            return
        self._running = True
        try:
            url = presign_medical_ws()
            self.log("Connecting WebSocket…")
            self.log(f"WS URL: {url.split('?')[0]}")
            
            # Provide the subprotocol header without enforcing client-side negotiation
            self.ws = create_connection(
                url,
                enable_multithread=True,
                header=["Sec-WebSocket-Protocol: aws.transcribe"],
            )
            self.log("Connected.")

            # Send brief silence (100ms) as AudioEvent so stream is not idle
            silence = b"\x00" * BYTES_PER_CHUNK
            msg = build_eventstream_message(
                {
                    ":message-type": "event",
                    ":event-type": "AudioEvent",
                    ":content-type": "application/octet-stream",
                },
                silence,
            )
            self.ws.send(msg, opcode=0x2)
        except Exception as e:
            self.log(f"WS connect failed: {e}")
            self._running = False
            return

        self.mic.start()
        self._send_t = threading.Thread(target=self._send_loop, daemon=True)
        self._recv_t = threading.Thread(target=self._recv_loop, daemon=True)
        self._send_t.start()
        self._recv_t.start()

    def stop(self):
        self._running = False
        try:
            self.mic.stop()
        except Exception:
            pass
        try:
            if self.ws:
                # allow a brief moment for any final chunks to flush
                time.sleep(0.1)
                # Signal EndOfStream per EventStream contract
                eos = build_eventstream_message(
                    {
                        ":message-type": "event",
                        ":event-type": "EndOfStream",
                    },
                    b"",
                )
                self._eos_sent = True
                self.ws.send(eos, opcode=0x2)
                time.sleep(0.1)
                self.ws.close()
        except Exception:
            pass
        self.log("Stopped.")

    def _send_loop(self):
        while self._running:
            try:
                chunk = self.audio_q.get(timeout=0.2)
                if not chunk:
                    continue
                msg = build_eventstream_message(
                    {
                        ":message-type": "event",
                        ":event-type": "AudioEvent",
                        ":content-type": "application/octet-stream",
                    },
                    chunk,
                )
                self.ws.send(msg, opcode=0x2)  # binary EventStream frame
            except queue.Empty:
                continue
            except WebSocketConnectionClosedException:
                self.log("WS closed during send.")
                break
            except Exception as e:
                self.log(f"Send err: {e}")
                break

    def _recv_loop(self):
        while self._running:
            try:
                raw = self.ws.recv()
                if not raw:
                    continue
                headers, payload = parse_eventstream_message(raw)
                if not headers:
                    # Show first bytes for diagnostics
                    self.log(f"Non-EventStream from server: {raw[:200]}")
                    continue
                if headers.get(":message-type") == "exception":
                    # Payload is JSON error
                    try:
                        err = json.loads(payload.decode("utf-8", errors="ignore"))
                    except Exception:
                        err = {"raw": payload[:200]}
                    # Suppress decode errors that sometimes arrive after EOS
                    msgtxt = (err.get("Message") or "").lower() if isinstance(err, dict) else ""
                    if self._eos_sent and "decode the audio stream" in msgtxt:
                        continue
                    self.log(f"Server error: {headers.get(':exception-type')} {err}")
                    continue
                if headers.get(":event-type") != "TranscriptEvent":
                    continue
                try:
                    evt = json.loads(payload.decode("utf-8"))
                except Exception:
                    self.log(f"Bad transcript JSON: {payload[:200]}")
                    continue
                results = evt.get("Transcript", {}).get("Results", [])
                for res in results:
                    alt = res["Alternatives"][0]
                    text = alt.get("Transcript", "")
                    if res.get("IsPartial", False):
                        self.set_partial(text)
                    else:
                        self.set_partial("")     # clear partial
                        self.append_final(text)  # commit final
            except WebSocketConnectionClosedException:
                self.log("WS closed during recv.")
                break
            except Exception as e:
                # Non-blocking: ignore transient timeouts, log others
                self.log(f"Recv err: {e}")
                time.sleep(0.01)

# ---------- Kivy UI ----------
class Root(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", spacing=8, padding=12, **kw)
        self.controls = BoxLayout(size_hint_y=None, height="44dp", spacing=8)
        self.btn_start = Button(text="Start (DICTATION)")
        self.btn_stop = Button(text="Stop", disabled=True)
        self.controls.add_widget(self.btn_start)
        self.controls.add_widget(self.btn_stop)

        self.partial_lbl = Label(text="[partial will appear here]", size_hint_y=None, height="24dp")
        self.final_txt = TextInput(text="", readonly=True, size_hint_y=0.55)
        self.log_txt = TextInput(text="", readonly=True, size_hint_y=0.35)

        self.add_widget(self.controls)
        self.add_widget(self.partial_lbl)
        self.add_widget(Label(text="Final transcript:", size_hint_y=None, height="24dp"))
        self.add_widget(self.final_txt)
        self.add_widget(Label(text="Log:", size_hint_y=None, height="24dp"))
        self.add_widget(self.log_txt)

        self.streamer = TranscribeStreamer(self.log_txt, self.partial_lbl, self.final_txt)
        self.btn_start.bind(on_release=self._start)
        self.btn_stop.bind(on_release=self._stop)

    def _start(self, *_):
        self.btn_start.disabled = True
        self.btn_stop.disabled = False
        self.streamer.start()

    def _stop(self, *_):
        self.btn_stop.disabled = True
        self.btn_start.disabled = False
        self.streamer.stop()

class RTMedicalApp(App):
    def build(self):
        return Root()

if __name__ == "__main__":
    RTMedicalApp().run()