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
        "userId": null,
        "timestamp": "{int(time.time())}",
        "rawTranscriptionId": null,
        "isOnline": true,
        "isOffline": false,
        "medicalNoteStructure": {{
            "progressNote": [
                {{
                    "noteId": null,
                    "timestamp": "{int(time.time())}",
                    "peopleInvoled": "",
                    "context": ""
                }}
            ],
            "patientObservations": [
                {{
                    "observationId": null,
                    "timestamp": "{int(time.time())}",
                    "bloodPressure": "",
                    "validty": "",
                    "otherObservations": ""
                }}
            ],
            "medicationAdministered": [
                {{
                    "medicationId": null,
                    "timestamp": "{int(time.time())}",
                    "medicineType": "",
                    "quantity": "",
                    "administrationType": ""
                }}
            ]
        }}
    }}

    Raw transcript:
    {transcript_text}
    """

    try:
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

        return json.loads(structured_text)
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return {"error": "invalid_json", "raw_text": structured_text}
    except Exception as e:
        print(f"Claude processing error: {e}")
        return {"error": "claude_error", "message": str(e)}

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "Backend is running", "endpoints": ["/transcribe"]})

@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    try:
        print("🎤 Received audio file for transcription")
        
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file provided"}), 400
            
        file = request.files["file"]
        print(f"📁 File name: {file.filename}")
        
        local_path = file.filename or "uploaded_audio.wav"
        file.save(local_path)
        print(f"💾 Saved to: {local_path}")

        # Convert audio
        audio = AudioSegment.from_file(local_path)
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
        converted_path = "converted.wav"
        audio.export(converted_path, format="wav")
        print(f"🔄 Audio converted and saved to: {converted_path}")

        # Upload to S3
        s3_key = f"uploads/{int(time.time())}.wav"
        s3.upload_file(converted_path, BUCKET_NAME, s3_key)
        print(f"☁️ Uploaded to S3: s3://{BUCKET_NAME}/{s3_key}")

        # Start transcription job
        job_name = f"medical-job-{int(time.time())}"
        job_uri = f"s3://{BUCKET_NAME}/{s3_key}"
        print(f"🏥 Starting transcription job: {job_name}")

        transcribe.start_medical_transcription_job(
            MedicalTranscriptionJobName=job_name,
            Media={"MediaFileUri": job_uri},
            MediaFormat="wav",
            LanguageCode="en-US",
            Specialty="PRIMARYCARE",
            Type="CONVERSATION",
            OutputBucketName=BUCKET_NAME
        )

        # Wait for completion
        print("⏳ Waiting for transcription to complete...")
        while True:
            status = transcribe.get_medical_transcription_job(
                MedicalTranscriptionJobName=job_name
            )
            job_status = status["MedicalTranscriptionJob"]["TranscriptionJobStatus"]
            print(f"📊 Job status: {job_status}")
            if job_status in ["COMPLETED", "FAILED"]:
                break
            time.sleep(5)

        if job_status == "COMPLETED":
            # Get transcript
            transcript_uri = status["MedicalTranscriptionJob"]["Transcript"]["TranscriptFileUri"]
            parsed = urllib.parse.urlparse(transcript_uri)
            raw_json_key = parsed.path.lstrip("/")

            if raw_json_key.startswith(BUCKET_NAME + "/"):
                raw_json_key = raw_json_key[len(BUCKET_NAME) + 1:]

            response = s3.get_object(Bucket=BUCKET_NAME, Key=raw_json_key)
            result_json = json.loads(response["Body"].read().decode("utf-8"))

            transcript_text = result_json["results"]["transcripts"][0]["transcript"]
            print(f"📝 Transcript: {transcript_text}")

            # Process with Claude
            print("🤖 Processing with Claude...")
            structured_data = format_with_claude(transcript_text)

            # Save structured data to S3
            if isinstance(structured_data, dict):
                structured_str = json.dumps(structured_data, indent=2)
            else:
                structured_str = str(structured_data)

            structured_key = f"structured/{int(time.time())}.json"
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=structured_key,
                Body=structured_str.encode("utf-8"),
                ContentType="application/json"
            )
            print(f"📋 Structured data saved to: s3://{BUCKET_NAME}/{structured_key}")

            # Clean up local files
            try:
                os.remove(local_path)
                os.remove(converted_path)
            except:
                pass

            return jsonify({
                "status": "success",
                "transcript": transcript_text,  # Added this!
                "raw_transcript_file": raw_json_key,
                "structured_transcript_file": structured_key,
                "structured_data": structured_data  # Added this!
            })
        else:
            print(f"❌ Transcription job failed: {job_status}")
            return jsonify({"status": "failed", "message": f"Transcription job {job_status}"})

    except Exception as e:
        print(f"❌ Backend error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
