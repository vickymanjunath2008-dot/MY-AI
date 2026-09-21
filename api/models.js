export const config = {
  runtime: "nodejs",
};

export default async function handler(req, res) {
  // 1. Enable full cross-origin access so LibreChat can connect
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  // 2. Extract the API key sent by LibreChat (or query param)
  const authHeader = req.headers.authorization || "";
  let apiKey = authHeader.replace("Bearer ", "").split(",")[0].trim();
  
  if (!apiKey && req.query.key) {
    apiKey = req.query.key;
  }

  if (!apiKey) {
    return res.status(400).json({ error: "Missing API Key" });
  }

  try {
    // 3. Directly ask Google's official REST endpoint for live models
    const googleRes = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`);
    const data = await googleRes.json();

    if (!googleRes.ok) {
      return res.status(googleRes.status).json({
        error: data.error?.message || "Failed to query Google for live models."
      });
    }

    // 4. Filter for text-generation Gemini models and format for LibreChat
    const modelsList = (data.models || [])
      .filter((m) => m.name.includes("gemini") && m.supportedGenerationMethods?.includes("generateContent"))
      .map((m) => {
        const id = m.name.replace("models/", "");
        return {
          id: id,
          object: "model",
          created: Math.floor(Date.now() / 1000),
          owned_by: "google",
          permission: [],
          root: id,
          parent: null
        };
      });

    return res.status(200).json({
      object: "list",
      data: modelsList
    });

  } catch (err) {
    return res.status(500).json({ error: err.message || "Internal server error querying Google." });
  }
}
