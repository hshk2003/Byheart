from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import speech_recognition as sr
import sounddevice as sd
import scipy.io.wavfile as wavfile
from difflib import SequenceMatcher

app = Flask(__name__)

# Function to connect to SQLite database
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Create the table (run this once or manage it through migrations)
def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                textbody TEXT NOT NULL,
                speech_text TEXT,
                accuracy REAL
            );
        ''')
        conn.commit()

# Function to record audio using sounddevice
def record_audio(file_name="mic_recording.wav", duration=10, fs=44100):
    print("Recording...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()  # Wait until recording is finished
    wavfile.write(file_name, fs, recording)  # Save as WAV file
    print("Recording complete, saved as", file_name)

# Function to recognize speech from the recorded WAV file
def speech_to_text():
    recognizer = sr.Recognizer()
    record_audio()  # Record audio and save as 'mic_recording.wav'

    # Convert speech to text
    with sr.AudioFile("mic_recording.wav") as source:
        audio = recognizer.record(source)  # Record the audio from the file
        try:
            speech_text = recognizer.recognize_google(audio)
            print(f"Recognized Speech: {speech_text}")
            return speech_text
        except sr.UnknownValueError:
            print("Speech Recognition could not understand audio")
            return "Recognition error"
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            return "Service error"

# Function to compare input text with speech text using difflib
def compare_texts(input_text, speech_text):
    similarity = SequenceMatcher(None, input_text, speech_text).ratio()
    return similarity * 100  # Convert to percentage

# Route for the home page
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle form submission for storing the input text
@app.route('/submit_text', methods=['POST'])
def submit_text():
    textbody = request.form['textbody']  # Get input text from form

    # Store the input text in the database (without accuracy/speech_text)
    with get_db_connection() as conn:
        conn.execute('INSERT INTO posts (textbody) VALUES (?)', (textbody,))
        conn.commit()

    return redirect(url_for('index'))

# Route to handle recording speech and storing recognized speech in the database
@app.route('/start_recording', methods=['POST'])
def start_recording():
    with get_db_connection() as conn:
        # Fetch the latest post (input text) from the database
        post = conn.execute('SELECT * FROM posts ORDER BY id DESC LIMIT 1').fetchone()

        if post:
            speech_text = speech_to_text()  # Get recognized speech
            conn.execute('UPDATE posts SET speech_text = ? WHERE id = ?', (speech_text, post['id']))
            conn.commit()

    return redirect(url_for('index'))

# Route for the results page that shows accuracy after comparing the texts
@app.route('/results')
def results():
    with get_db_connection() as conn:
        # Fetch the latest post with textbody and speech_text
        post = conn.execute('SELECT * FROM posts ORDER BY id DESC LIMIT 1').fetchone()

        if post and post['speech_text']:  # Ensure both input and recognized text exist
            accuracy = compare_texts(post['textbody'], post['speech_text'])
            conn.execute('UPDATE posts SET accuracy = ? WHERE id = ?', (accuracy, post['id']))
            conn.commit()
        else:
            accuracy = None

    return render_template('results.html', post=post, accuracy=accuracy)

# Initialize the database
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
