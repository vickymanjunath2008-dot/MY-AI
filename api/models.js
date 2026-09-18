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
    // Direct Google API call from Vercel backend (No CORS issues)
    const googleRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey.trim()}`);
    const data = await googleRes.json();

    if (!googleRes.ok) {
      return res.status(googleRes.status).json({ error: data.error?.message || "Failed to query Google." });
    }

    const availableModels = [];
    if (data.models) {
      data.models.forEach((m) => {
        const name = m.name.replace("models/", "");
        if (name.includes("gemini") && m.supportedGenerationMethods?.includes("generateContent")) {
          availableModels.push(name);
        }
      });
    }

    return res.status(200).json({ models: availableModels.sort() });
  } catch (err) {
    return res.status(500).json({ error: err.message || "Internal server error." });
  }
}
