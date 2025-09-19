from flask import Flask, request, jsonify
import boto3
import time
import json
import os
import urllib.parse
import re
from pydub import AudioSegment

app = Flask(__name__)

s3 = boto3.client("s3", region_name="ap-southeast-2")
transcribe = boto3.client("transcribe", region_name="ap-southeast-2")
bedrock = boto3.client("bedrock-runtime", region_name="ap-southeast-2")

BUCKET_NAME = "ps2511-medical-buckets"

CLAUDE_37_SONNET_ARN = (
    "arn:aws:bedrock:ap-southeast-2:581867121100:inference-profile/"
    "apac.anthropic.claude-3-7-sonnet-20250219-v1:0"
)

def clean_json_output(text: str) -> str:
    """
    Extract JSON from Claude's response.
    Removes code fences and extra text.
    """

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*", "", text, flags=re.MULTILINE)
        text = re.sub(r"```$", "", text, flags=re.MULTILINE).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return text[start:end+1]
    return text 

def format_with_claude(transcript_text):
    prompt = f"""
    You are a medical assistant AI. Take the raw transcript and convert it into JSON
    following this schema exactly.

    Rules:
    - Extract only real values from the transcript.
    - If information is missing, set the field to null or "".
    - Do not add examples or placeholders.
    - Return only valid JSON, nothing else.

    Schema:
    {{
        "userId": ,
        "timestamp": ,
        "rawTranscriptionId": ,
        "isOnline": ,
        "isOffline": ,
        "medicalNoteStructure": {{
            "progressNote": [
                {{
                    "noteId": ,
                    "timestamp": ,
                    "peopleInvoled": ,
                    "context":
                }}
            ],
            "patientObservations": [
                {{
                    "observationId": ,
                    "timestamp": ,
                    "bloodPressure": ,
                    "validty": ,
                    "otherObservations":
                }}
            ],
            "medicationAdministered": [
                {{
                    "medicationId": ,
                    "timestamp": ,
                    "medicineType": ,
                    "quantity": ,
                    "administrationType":
                }}
            ]
        }}
    }}

    Raw transcript:
    {transcript_text}
    """

    response = bedrock.invoke_model(
        modelId=CLAUDE_37_SONNET_ARN,
        accept="application/json",
        contentType="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "temperature": 0,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        })
    )

    raw_output = response["body"].read().decode("utf-8")
    result = json.loads(raw_output)
    structured_text = result["content"][0]["text"].strip()

    if structured_text.startswith("```"):
        structured_text = structured_text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(structured_text)
    except json.JSONDecodeError:
        return {"error": "invalid_json", "raw_text": structured_text}


@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    file = request.files["file"]
    local_path = file.filename
    file.save(local_path)

    audio = AudioSegment.from_file(local_path)
    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
    converted_path = "converted.wav"
    audio.export(converted_path, format="wav")

    s3_key = f"uploads/{int(time.time())}.wav"
    s3.upload_file(converted_path, BUCKET_NAME, s3_key)

    job_name = f"medical-job-{int(time.time())}"
    job_uri = f"s3://{BUCKET_NAME}/{s3_key}"

    transcribe.start_medical_transcription_job(
        MedicalTranscriptionJobName=job_name,
        Media={"MediaFileUri": job_uri},
        MediaFormat="wav",
        LanguageCode="en-US",
        Specialty="PRIMARYCARE",
        Type="CONVERSATION",
        OutputBucketName=BUCKET_NAME
    )

    while True:
        status = transcribe.get_medical_transcription_job(
            MedicalTranscriptionJobName=job_name
        )
        job_status = status["MedicalTranscriptionJob"]["TranscriptionJobStatus"]
        if job_status in ["COMPLETED", "FAILED"]:
            break
        time.sleep(5)

    if job_status == "COMPLETED":
        transcript_uri = status["MedicalTranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        parsed = urllib.parse.urlparse(transcript_uri)
        raw_json_key = parsed.path.lstrip("/")

        if raw_json_key.startswith(BUCKET_NAME + "/"):
            raw_json_key = raw_json_key[len(BUCKET_NAME) + 1:]

        response = s3.get_object(Bucket=BUCKET_NAME, Key=raw_json_key)
        result_json = json.loads(response["Body"].read().decode("utf-8"))

        print("Transcript URI:", transcript_uri)
        print("Parsed Key:", raw_json_key)

        transcript_text = result_json["results"]["transcripts"][0]["transcript"]

        structured_data = format_with_claude(transcript_text)
        print("Raw output:", transcript_text)

        if isinstance(structured_data, dict):
            structured_str = json.dumps(structured_data, indent=2)
        else:
            structured_str = structured_data

        structured_key = f"structured/{int(time.time())}.json"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=structured_key,
            Body=structured_str.encode("utf-8"),
            ContentType="application/json"
        )

        return jsonify({
            "status": "success",
            "raw_transcript_file": raw_json_key,
            "structured_transcript_file": structured_key
        })

    return jsonify({"status": "failed"})

if __name__ == "__main__":
    app.run(debug=True)
