import { GoogleGenAI } from "@google/genai";

export const config = {
  runtime: "nodejs",
};

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const {
    messages = [],
    apiKeys = [],
    model = "gemini-2.0-flash",
    systemInstruction = "",
    temperature = 0.6,
    safetyLevel = "BLOCK_NONE",
    vaultLore = "",
    thinkingBudget = 0
  } = req.body;

  if (!apiKeys || apiKeys.length === 0) {
    return res.status(400).json({ error: "No API keys provided." });
  }

  // Set SSE headers for fluid word-by-word streaming
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");

  // 1. Assemble Payload: Lore Vault + Capped 60-turn Window
  const contents = [];
  
  if (vaultLore && vaultLore.trim()) {
    contents.push({
      role: "user",
      parts: [{ text: `[LORE VAULT & BACKGROUND RULES]:\n${vaultLore.trim()}` }]
    });
    contents.push({
      role: "model",
      parts: [{ text: "Understood. Maintaining continuity with the vault." }]
    });
  }

  // Enforce strict 60-message sliding window
  const recentMessages = messages.slice(-60);
  for (const msg of recentMessages) {
    contents.push({
      role: msg.role === "user" ? "user" : "model",
      parts: [{ text: msg.content }]
    });
  }

  // 2. Unrestricted Safety Settings
  const safetySettings = [
    { category: "HARM_CATEGORY_HARASSMENT", threshold: safetyLevel },
    { category: "HARM_CATEGORY_HATE_SPEECH", threshold: safetyLevel },
    { category: "HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold: safetyLevel },
    { category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: safetyLevel }
  ];

  // 3. Failover Loop across all 5 Keys
  let success = false;
  let lastError = null;

  for (let i = 0; i < apiKeys.length; i++) {
    const key = apiKeys[i].trim();
    if (!key) continue;

    try {
      const ai = new GoogleGenAI({ apiKey: key });
      
      const generateConfig = {
        temperature: parseFloat(temperature) || 0.6,
        safetySettings
      };

      if (systemInstruction && systemInstruction.trim()) {
        generateConfig.systemInstruction = systemInstruction.trim();
      }

      // Optional Thinking Level Budget
      if (thinkingBudget > 0) {
        generateConfig.thinkingConfig = { thinkingBudget: parseInt(thinkingBudget, 10) };
      }

      const responseStream = await ai.models.generateContentStream({
        model,
        contents,
        config: generateConfig
      });

      // Stream text chunks back to your phone screen
      for await (const chunk of responseStream) {
        const text = chunk.text;
        if (text) {
          res.write(`data: ${JSON.stringify({ text, activeKeyIndex: i })}\n\n`);
        }
      }

      res.write("data: [DONE]\n\n");
      res.end();
      success = true;
      break;

    } catch (err) {
      console.warn(`Key #${i + 1} failed, rolling to next key:`, err.message);
      lastError = err.message;
      continue;
    }
  }

  if (!success) {
    res.write(`data: ${JSON.stringify({ error: lastError || "All API keys in pool failed." })}\n\n`);
    res.write("data: [DONE]\n\n");
    res.end();
  }
}
