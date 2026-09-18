import { GoogleGenAI } from "@google/genai";

export const config = {
  runtime: "nodejs",
};

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { apiKey } = req.body;
  if (!apiKey || !apiKey.trim()) {
    return res.status(400).json({ error: "No API key provided." });
  }

  try {
    const ai = new GoogleGenAI({ apiKey: apiKey.trim() });
    const response = await ai.models.list();
    
    const availableModels = [];
    for await (const m of response) {
      const name = m.name.replace("models/", "");
      // Only include Gemini models that generate content
      if (name.includes("gemini")) {
        availableModels.push(name);
      }
    }

    return res.status(200).json({ models: availableModels.sort() });
  } catch (err) {
    return res.status(500).json({ error: err.message || "Failed to fetch models." });
  }
}
