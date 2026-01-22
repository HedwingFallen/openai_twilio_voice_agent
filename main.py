import asyncio
import base64
import json
import os
import signal
from typing import Optional

import websockets
from websockets.server import WebSocketServerProtocol
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = os.getenv("MODEL", "gpt-realtime")
VOICE = os.getenv("VOICE", "marin")

if not OPENAI_API_KEY:
    raise RuntimeError("Faltou OPENAI_API_KEY no .env")

OPENAI_WS_URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"

# -----------------------------
# Util: mensagens Twilio
# -----------------------------
def twilio_media(stream_sid: str, payload_b64: str) -> str:
    return json.dumps({
        "event": "media",
        "streamSid": stream_sid,
        "media": {"payload": payload_b64},
    })

def twilio_clear(stream_sid: str) -> str:
    # Interrompe o áudio bufferizado do lado do Twilio (barge-in)
    return json.dumps({
        "event": "clear",
        "streamSid": stream_sid,
    })


# -----------------------------
# Bridge: Twilio <-> OpenAI
# -----------------------------
async def handle_call(twilio_ws: WebSocketServerProtocol):
    stream_sid: Optional[str] = None
    call_sid: Optional[str] = None

    # Conecta no OpenAI Realtime (server-side)
    async with websockets.connect(
        OPENAI_WS_URL,
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        ping_interval=20,
        ping_timeout=20,
        max_size=2**23,
    ) as openai_ws:

        # Configura sessão: áudio PCMU (compatível com Twilio Media Streams)
        # Exemplo de session.update com `audio/pcmu` e VAD semântico citeturn4view0
        session_update = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": MODEL,
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcmu"},
                        "turn_detection": {"type": "semantic_vad"},
                    },
                    "output": {
                        "format": {"type": "audio/pcmu"},
                        "voice": VOICE,
                    },
                },
                "instructions": (
                    "Você é um atendente virtual educado e objetivo. "
                    "Fale em português do Brasil. "
                    "Se algo estiver ambíguo, faça uma pergunta curta para confirmar."
                ),
            },
        }
        await openai_ws.send(json.dumps(session_update))

        # Estado pra barge-in
        responding = False

        async def twilio_to_openai():
            nonlocal stream_sid, call_sid
            async for raw in twilio_ws:
                msg = json.loads(raw)

                event = msg.get("event")
                if event == "start":
                    stream_sid = msg["start"]["streamSid"]
                    call_sid = msg["start"].get("callSid")
                    print(f"[twilio] start streamSid={stream_sid} callSid={call_sid}")
                elif event == "media":
                    # Twilio manda áudio base64 `audio/x-mulaw` 8kHz citeturn0search1
                    payload_b64 = msg["media"]["payload"]

                    # OpenAI Realtime recebe chunks base64 no input_audio_buffer.append citeturn2view4
                    await openai_ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": payload_b64,
                    }))
                elif event == "stop":
                    print("[twilio] stop")
                    break

        async def openai_to_twilio():
            nonlocal responding
            async for raw in openai_ws:
                msg = json.loads(raw)
                t = msg.get("type")

                # Debug leve (descomente se quiser barulho)
                # if t not in ("response.output_audio.delta",):
                #     print("[openai]", t)

                # Barge-in: se o usuário começou a falar, corta áudio que já estava tocando
                if t == "input_audio_buffer.speech_started":
                    if responding and stream_sid:
                        # Cancela resposta em andamento
                        await openai_ws.send(json.dumps({"type": "response.cancel"}))
                        # Limpa buffer do Twilio
                        await twilio_ws.send(twilio_clear(stream_sid))
                        responding = False

                # Áudio do modelo (em chunks)
                if t == "response.output_audio.delta":
                    if not stream_sid:
                        continue
                    responding = True
                    delta_b64 = msg.get("delta")
                    if delta_b64:
                        await twilio_ws.send(twilio_media(stream_sid, delta_b64))

                if t == "response.output_audio.done" or t == "response.done":
                    responding = False

        # Roda as duas pontas juntas
        await asyncio.gather(twilio_to_openai(), openai_to_twilio())


async def ws_router(ws: WebSocketServerProtocol, path: str):
    if path != "/twilio":
        await ws.close(code=1008, reason="Use /twilio")
        return
    await handle_call(ws)


async def main():
    server = await websockets.serve(
        ws_router,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=20,
        max_size=2**23,
    )

    print("Servidor WS pronto. Sockets abertos:")
    for s in server.sockets:
        print(" -", s.getsockname())

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())