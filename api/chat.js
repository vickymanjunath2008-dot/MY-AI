export const config = {
  runtime: "nodejs",
};

export default async function handler(req, res) {
  // 1. Enable full CORS so LibreChat can stream seamlessly
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const body = req.body || {};
  const rawMessages = body.messages || [];
  const requestedModel = body.model || "gemini-2.0-flash";
  const temperature = parseFloat(body.temperature) ?? 0.6;
  const stream = body.stream !== false;

  // 2. EXTRACT DYNAMIC KEY POOL (Accepts comma-separated keys in Authorization header)
  const authHeader = req.headers.authorization || "";
  const keyPool = authHeader
    .replace("Bearer ", "")
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);

  if (keyPool.length === 0) {
    return res.status(400).json({
      error: {
        message: "No Gemini API keys provided. Please provide them in settings.",
        type: "invalid_request_error"
      }
    });
  }

  // 3. ENFORCE 100-MESSAGE VERBATIM SLIDING WINDOW
  const windowedMessages = rawMessages.slice(-100);

  // 4. CONVERT TO GOOGLE NATIVE REST PAYLOAD
  const contents = [];
  let systemInstructionText = "";

  for (const msg of windowedMessages) {
    if (msg.role === "system") {
      systemInstructionText += (systemInstructionText ? "\n\n" : "") + msg.content;
    } else {
      contents.push({
        role: msg.role === "user" ? "user" : "model",
        parts: [{ text: msg.content }]
      });
    }
  }

  if (contents.length === 0) {
    contents.push({ role: "user", parts: [{ text: "Hello" }] });
  }

  // 5. NATIVE UNRESTRICTED GOOGLE SAFETY SETTINGS (BLOCK_NONE)
  const safetySettings = [
    { category: "HARM_CATEGORY_HARASSMENT", threshold: "BLOCK_NONE" },
    { category: "HARM_CATEGORY_HATE_SPEECH", threshold: "BLOCK_NONE" },
    { category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: "BLOCK_NONE" },
    { category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "BLOCK_NONE" }
  ];

  const payload = {
    contents: contents,
    generationConfig: {
      temperature: temperature
    },
    safetySettings: safetySettings
  };

  if (systemInstructionText.trim()) {
    payload.systemInstruction = {
      parts: [{ text: systemInstructionText.trim() }]
    };
  }

  // 6. FAILOVER EXECUTION LOOP ACROSS ENTIRE KEY POOL
  let lastError = null;
  let success = false;

  for (let i = 0; i < keyPool.length; i++) {
    const currentKey = keyPool[i];
    const action = stream ? "streamGenerateContent?alt=sse" : "generateContent";
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${requestedModel}:${action}&key=${currentKey}`;

    try {
      const googleRes = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!googleRes.ok) {
        const errorData = await googleRes.json().catch(() => ({}));
        lastError = errorData.error?.message || `HTTP ${googleRes.status}`;
        console.warn(`Key #${i + 1} hit error: ${lastError}. Silently rolling to next key...`);
        // If 429 (Rate Limit) or 503 (Overload), loop immediately to next key!
        continue;
      }

      // --- WORD-BY-WORD STREAMING (SSE) ---
      if (stream) {
        res.setHeader("Content-Type", "text/event-stream");
        res.setHeader("Cache-Control", "no-cache, no-transform");
        res.setHeader("Connection", "keep-alive");

        const reader = googleRes.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop();

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data: ")) {
              try {
                const parsed = JSON.parse(trimmed.substring(6));
                const textChunk = parsed.candidates?.[0]?.content?.parts?.[0]?.text;

                if (textChunk) {
                  const sseData = {
                    id: "chatcmpl-" + Date.now(),
                    object: "chat.completion.chunk",
                    created: Math.floor(Date.now() / 1000),
                    model: requestedModel,
                    choices: [
                      {
                        index: 0,
                        delta: { content: textChunk },
                        finish_reason: null
                      }
                    ]
                  };
                  res.write(`data: ${JSON.stringify(sseData)}\n\n`);
                }
              } catch (e) {}
            }
          }
        }

        const doneData = {
          id: "chatcmpl-" + Date.now(),
          object: "chat.completion.chunk",
          created: Math.floor(Date.now() / 1000),
          model: requestedModel,
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }]
        };
        res.write(`data: ${JSON.stringify(doneData)}\n\n`);
        res.write("data: [DONE]\n\n");
        res.end();
        success = true;
        break;

      } else {
        // --- NON-STREAMING RESPONSE ---
        const data = await googleRes.json();
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text || "";

        return res.status(200).json({
          id: "chatcmpl-" + Date.now(),
          object: "chat.completion",
          created: Math.floor(Date.now() / 1000),
          model: requestedModel,
          choices: [
            {
              index: 0,
              message: { role: "assistant", content: text },
              finish_reason: "stop"
            }
          ],
          usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
        });
      }

    } catch (networkErr) {
      lastError = networkErr.message;
      console.warn(`Network error on Key #${i + 1}: ${lastError}. Retrying next...`);
      continue;
    }
  }

  if (!success) {
    return res.status(500).json({
      error: {
        message: `All API keys in pool failed or exhausted. Last Google response: ${lastError}`,
        type: "rate_limit_error"
      }
    });
  }
}
