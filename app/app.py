import os
from pytubefix import YouTube, Playlist
import whisper
import torch, gc
import subprocess
import time
import re

import psycopg2
from psycopg2.extras import RealDictCursor
from ollama import chat
from ollama import ChatResponse

# Database connection
def get_db_connection():
    return psycopg2.connect(
        dbname="snipscribe",
        user="root",
        password="root",
        host="localhost",
        port=5432
    )

def check_summary():
    print("Checking for pending summaries...")
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM "summaries" WHERE status = %s', ('PENDING',))
    summary = cursor.fetchone()
    if not summary:
        cursor.close()
        conn.close()
        return None
    
    cursor.execute('SELECT * FROM "videos" WHERE id = %s', (summary['video_id'],))
    video = cursor.fetchone()

    cursor.execute('SELECT * FROM "summary_requests" WHERE id = %s', (summary['summary_request_id'],))
    request = cursor.fetchone()

    cursor.close()
    conn.close()
    return {
        'summary': summary,
        'video': video,
        'language': request['language'],
    }

# Function to create a folder to store the downloaded files
def create_folder():
    print("Creating folder...")
    global path
    path = os.path.join(os.getcwd(), 'youtube_downloads')
    if not os.path.exists(path):
        os.makedirs(path)

# Function to download the video or playlist from pytube
def pytube_downloader(url, path):
    print("Downloading...")
    title = ''
    yt = YouTube(url, 'WEB')
    ys = yt.streams.get_audio_only()
    audio_file = ys.download(path)
    title = yt.title

    return title, audio_file

# Function to transcribe the audio files using Whisper
def transcribe_text(audio_file):
    print("Transcribing...")
    transcription = ''
    try:
        model = whisper.load_model("large", device="cuda")
        result = model.transcribe(audio_file)
        transcription = result["text"]
        del model
        del result
        clear_cache()
    except Exception as e:
        model = whisper.load_model("large", device="cpu")
        result = model.transcribe(audio_file)
        transcription = result["text"]
        del model
        del result
        clear_cache()

    os.remove(audio_file)
    return transcription

# Function to clear the cache from memory
def clear_cache():
    gc.collect()
    torch.cuda.empty_cache()

# Function to transcribe the audio file using Ollama
def summarize_text(trans, language):
    time.sleep(10)
    print("Summarizing...")
    # Start the Ollama server
    try:
        process = subprocess.Popen("ollama serve", shell=True)
    except Exception as e:
        print(f"Error starting Ollama server: {e}")

    # Wait a few seconds to ensure the server is up
    time.sleep(3)

    # Call the Ollama chat API
    response: ChatResponse = chat(model='qwen3', messages=[
            { 'role': 'system', 'content': '/no_think' },
            {
                'role': 'user',
                'content': f"""
                            You are a highly focused assistant. Follow these steps exactly:

                            1. **Language**  
                            Respond **only** in the language specified by `{language}`.

                            2. **Summary**  
                            First, give a very concise paragraph summarizing the transcript in `{language}`.

                            3. **Key Points**  
                            - Automatically translate the phrase “Key Points” into `{language}` and use that as your heading.  
                            - Under that heading, list the most important takeaways as bullet points—in `{language}`.

                            4. **No Extras**  
                            Do not include any additional commentary, explanations, or formatting beyond the summary paragraph, the translated heading, and the bullet list.

                            **Transcript:**  
                            {trans}
                            """
            },
        ])

    # Clean the response by removing the <think>...</think> section
    content = response['message']['content']
    cleaned_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
    
    clear_cache()
    return cleaned_content.strip()

def save_summary(id, summary, title):
    print("Saving summary...")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE "summaries" SET status = %s, body = %s, title = %s WHERE id = %s',
        ('COMPLETED', summary, title, id)
    )
    cursor.execute(
        '''INSERT INTO "notifications" (user_id, summary_id)
           SELECT sr.user_id, s.id FROM "summaries" s
           JOIN "summary_requests" sr ON sr.id = s.summary_request_id
           WHERE s.id = %s
           ON CONFLICT (summary_id) DO NOTHING''',
        (id,)
    )
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    create_folder()
    while True:
        result = check_summary()
        if result:
            url = result['video']['url']
            id = result['summary']['id']
            language = result['language']
            title, audio_file = pytube_downloader(url, path)
            transcription = transcribe_text(audio_file)
            summary = summarize_text(transcription, language)
            save_summary(id, summary, title)
        else:
            print("No pending summaries found.")
        time.sleep(60)