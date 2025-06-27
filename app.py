from flask import Flask, jsonify, request
from flask_cors import CORS
from pytubefix import YouTube
from pytubefix.innertube import _default_clients
from openai import OpenAI

# Initialize Flask app
app = Flask(__name__)
CORS(app, supports_credentials=True)

# Initialize OpenAI client
client = OpenAI(api_key="YOUR_API_KEY")  # Replace with your actual API key


def clean_subtitles(srt_text):
    lines = srt_text.split('\n')
    return '\n'.join([
        line for line in lines
        if line.strip() and '-->' not in line and not line.strip().isdigit()
    ])


@app.route('/subtitles', methods=['POST', 'OPTIONS'])
def get_subtitles():
    data = request.get_json()
    if not data or 'video_url' not in data:
        return jsonify({'error': 'Missing video_url in request'}), 400

    video_url = data['video_url']
    lang = data.get('lang', 'en')

    try:
        yt = YouTube(video_url)
        caption = yt.captions.get(lang) or yt.captions.get(f"a.{lang}") or next(iter(yt.captions.values()), None)
        if caption:
            srt = clean_subtitles(caption.generate_srt_captions())
            return jsonify({'subtitles': srt})
        else:
            return jsonify({'error': 'No subtitles found for this video'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/summary', methods=['POST'])
def get_summary():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'Missing subtitles text in request'}), 400

    text = data['text']

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",  # Or "gpt-4", depending on your usage
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert summarizer. Your task is to create a comprehensive, "
                        "insightful, and well-organized summary of a YouTube video's content, based on its subtitles. "
                        "Your summary should be written in clear, engaging English and formatted in markdown. "
                        "Use appropriate markdown headers, bullet points, and bold or italic emphasis to highlight key ideas, "
                        "insights, and takeaways. Structure the summary logically, including an introduction, main points, and a conclusion or key lessons. "
                        "Avoid copying verbatim; instead, synthesize and clarify."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Here are the subtitles:\n\n" + text
                    ),
                },
            ],
            max_tokens=1000
        )
        return jsonify({'summary': response.choices[0].message.content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ✅ NEW: Direct summary route from YouTube video URL
@app.route('/yt-summary', methods=['POST'])
def summarize_youtube_video():
    data = request.get_json()
    if not data or 'video_url' not in data:
        return jsonify({'error': 'Missing video_url in request'}), 400

    video_url = data['video_url']
    lang = data.get('lang', 'en')

    try:
        yt = YouTube(video_url)
        caption = yt.captions.get(lang) or yt.captions.get(f"a.{lang}") or next(iter(yt.captions.values()), None)
        if not caption:
            return jsonify({'error': 'No subtitles found for this video'}), 404

        srt = clean_subtitles(caption.generate_srt_captions())

        # AI Summary
        response = client.chat.completions.create(
            model="deepseek-chat",  # Or "gpt-4", if using OpenAI directly
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert summarizer. Your task is to create a comprehensive, "
                        "insightful, and well-organized summary of a YouTube video's content, based on its subtitles. "
                        "Your summary should be written in clear, engaging English and formatted in markdown. "
                        "Use appropriate markdown headers, bullet points, and bold or italic emphasis to highlight key ideas, "
                        "insights, and takeaways."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Here are the subtitles:\n\n" + srt
                    ),
                },
            ],
            max_tokens=1000
        )

        return jsonify({
            'video_url': video_url,
            'summary': response.choices[0].message.content
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')  # Set this to your frontend domain in production
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
