# Agente de Voz (Twilio Media Streams + OpenAI Realtime) — do zero

## O que isso faz
- Recebe áudio de uma ligação (Twilio Media Streams)
- Envia o áudio pra OpenAI Realtime via WebSocket
- Recebe áudio de volta (voz do modelo) e toca na ligação

**Formato de áudio:** PCMU / G.711 u-law (o mesmo `audio/x-mulaw` do Twilio), então não precisa transcodificar.  
Twilio exige `audio/x-mulaw` 8kHz nos frames enviados de volta.  
OpenAI Realtime suporta `audio/pcmu`.  
Fontes: Twilio Media Streams `audio/x-mulaw` 8000 citeturn0search1, OpenAI session.update com `audio/pcmu` citeturn4view0.

## Arquivos
- `main.py` → servidor WebSocket (Twilio ↔ OpenAI)
- `twiml.xml` → TwiML pra você colar no Twilio (Webhook / Voice URL)
- `.env.example` → exemplo de variáveis
- `requirements.txt`

## Setup rápido
1) Crie e ative um venv (opcional, mas recomendado)
```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate
```

2) Instale deps
```bash
pip install -r requirements.txt
```

3) Crie `.env` (copie do `.env.example`) e coloque sua chave:
```env
OPENAI_API_KEY=...
```

4) Rode o servidor
```bash
python main.py
```

Ele vai subir em `ws://localhost:8000/twilio`

## Expor para o Twilio (produção / teste)
Twilio precisa de **WSS público**. Pra testar local:
- use um túnel tipo ngrok/cloudflared (WSS)
- a URL final vai ficar tipo: `wss://SEU-DOMINIO/twilio`

## Configurar Twilio
No console do Twilio (Voice > Phone Numbers):
- em "A CALL COMES IN" selecione **TwiML Bin** ou **Webhook** que retorne o XML do `twiml.xml`
- troque `YOUR_WSS_URL` pela sua URL WSS pública

## Debug
- Se não ouvir nada: confira se a URL é `wss://...` e se o caminho `/twilio` bate.
- Se a IA responde mas o áudio sai mudo: confirme que o `audio/pcmu` está configurado na session.update e que você está enviando `media` pro Twilio.

Boa diversão. Telefone + IA é a mistura mais caótica e poderosa do rolê.
