import os, requests
r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, params={"pageSize": 200}, timeout=60)
for m in r.json().get("models", []):
    if "generateContent" in m.get("supportedGenerationMethods", []) and ("flash" in m["name"] or "gemma" in m["name"]):
        print(m["name"], "|", m.get("displayName"))
