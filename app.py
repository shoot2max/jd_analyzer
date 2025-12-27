import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

from prompts import SYSTEM_PROMPT

# Load environment variables (works locally with .env; on Render uses dashboard vars)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY as an environment variable.")

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

# Allow requests from any origin (Netlify frontend)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Portable log directory (works on Windows + Render Linux)
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


@app.route("/analyze-job", methods=["POST", "OPTIONS"])
def analyze_job():
    # Handle CORS preflight
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response, 200

    data = request.get_json(silent=True) or {}
    jd = (data.get("job_description") or "").strip()

    if len(jd) < 50:
        return jsonify({"error": "Please provide a longer job description."}), 400

    # Optional: truncate very long JDs to manage token cost
    max_chars = 4000
    truncated = False
    if len(jd) > max_chars:
        jd = jd[:max_chars] + "\n\n[Truncated for analysis]"
        truncated = True

    try:
        # Call OpenAI Responses API
        completion = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"Here is the job description:\n\n{jd}",
                },
            ],
            max_output_tokens=1200,
            temperature=0.5,
        )

        # Extract from Responses API format
        content_item = completion.output[0].content[0].text
        analysis_markdown = content_item  # already a string

        # Basic logging for debugging / iteration
        log_path = os.path.join(LOG_DIR, "last_analysis.md")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=== JOB DESCRIPTION ===\n\n")
            f.write(jd)
            f.write("\n\n=== ANALYSIS ===\n\n")
            f.write(analysis_markdown)

        return jsonify(
            {
                "analysis_markdown": analysis_markdown,
                "truncated": truncated,
            }
        )

    except Exception as e:
        print("Error analyzing job:", e)
        return jsonify({"error": "Analysis failed. Please try again."}), 500


if __name__ == "__main__":
    # Local dev server
    app.run(host="0.0.0.0", port=8000, debug=True)
