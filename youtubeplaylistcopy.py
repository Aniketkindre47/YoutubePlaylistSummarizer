import streamlit as st
import os
import re
import pandas as pd
from googleapiclient.discovery import build
import google.generativeai as genai


# --- Configuration & API Key Setup ---
from dotenv import load_dotenv

load_dotenv()


# # Load API keys from environment variables
# GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")


# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="YouTube Playlist Summarizer", page_icon="🎬", layout="wide"
)

# Add API key input fields in the sidebar
with st.sidebar:
    st.header("API Configuration")
    GEMINI_API_KEY = st.text_input("Gemini API Key", type="password")
    YOUTUBE_API_KEY = st.text_input("YouTube API Key", type="password")

    if not GEMINI_API_KEY or not YOUTUBE_API_KEY:
        st.warning("Please enter both API keys to use the application.")
        st.stop()

# --- Main Content ---
st.title("🎵 YouTube Playlist Generator")
st.markdown(
    """
    This application allows you to enter a YouTube playlist URL, extract all video links,
    and then summarize each video using the Gemini AI.
    """
)

# --- Instructions for API Keys ---
st.header("API Key Setup")
st.info(
    """
    To use this application, you need to set up two API keys as environment variables(.env file):
    1.  **`GEMINI_API_KEY`**: From Google Cloud (enable Generative Language API or Gemini API).
    2.  **`YOUTUBE_API_KEY`**: From Google Cloud (enable YouTube Data API v3).
    """
)

# --- Initialize APIs ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",  # You can choose other models like 'gemini-pro'
    )
else:
    st.error(
        "Gemini API key not found. Please enter your Gemini API key in the sidebar."
    )
    gemini_model = None


# --- Helper Functions (Reused from previous code) ---


@st.cache_data(show_spinner=False)  # Cache results to avoid re-fetching on rerun
def get_youtube_playlist_id(url):
    """Extracts the YouTube playlist ID from a URL."""
    match = re.search(r"(?:list=)([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    return None


@st.cache_data(show_spinner=False)  # Cache results
def get_playlist_video_urls(playlist_id):
    """Fetches all video URLs from a given YouTube playlist ID."""
    if not YOUTUBE_API_KEY:
        st.error(
            "YouTube Data API key not found. Please enter your YouTube API key in the sidebar."
        )
        return []

    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        video_urls = []
        next_page_token = None

        while True:
            request = youtube.playlistItems().list(
                part="contentDetails,snippet",  # Include snippet to get video title
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            )
            response = request.execute()

            for item in response["items"]:
                video_id = item["contentDetails"]["videoId"]
                video_title = item["snippet"]["title"]
                video_urls.append(
                    {
                        "video_id": video_id,
                        "title": video_title,
                        "url": f"youtu.be/{video_id}",
                    }
                )

            next_page_token = response.get("nextPageToken")

            if not next_page_token:
                break
        return video_urls

    except Exception as e:
        st.error(f"Error fetching playlist videos: {e}")
        return []


@st.cache_data(show_spinner=False)  # Cache results
def get_video_details(video_id):
    """Fetches video details using YouTube API."""
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        request = youtube.videos().list(
            part="snippet,contentDetails",
            id=video_id
        )
        response = request.execute()
        
        if response['items']:
            video = response['items'][0]
            return {
                'title': video['snippet']['title'],
                'description': video['snippet']['description'],
                'channel': video['snippet']['channelTitle'],
                'published_at': video['snippet']['publishedAt']
            }
        return None
    except Exception as e:
        return None


@st.cache_data(show_spinner=False)  # Cache results
def summarize_text_with_gemini(url):
    """Summarizes information about the video using Gemini."""
    if not gemini_model:
        return "Gemini model not initialized."

    try:
        # Extract video ID from URL
        video_id = url.split('/')[-1]
        
        # Get video details
        video_details = get_video_details(video_id)
        
        if not video_details:
            return "Could not fetch video details."

        prompt = f"""Please provide a concise summary of this YouTube video based on its details:

Title: {video_details['title']}
Channel: {video_details['channel']}
Description: {video_details['description']}

Please summarize the main topic and key points that might be covered in this video."""
        
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error summarizing: {e}"


# --- Streamlit UI ---

playlist_url_input = st.text_input(
    "Enter YouTube Playlist URL:",
    placeholder="e.g., youtu.be/4",
)

if st.button("Get Summaries"):
    if not GEMINI_API_KEY or not YOUTUBE_API_KEY:
        st.warning("Please enter both API keys in the sidebar to proceed.")
    elif not playlist_url_input:
        st.warning("Please enter a YouTube playlist URL.")
    else:
        playlist_id = get_youtube_playlist_id(playlist_url_input)

        if not playlist_id:
            st.error("Invalid YouTube playlist URL. Please ensure it contains 'list='.")
        else:
            st.subheader(f"Summaries for Playlist ID: `{playlist_id}`")
            st.info(
                "Fetching video details and summarizing. This might take a while for large playlists..."
            )

            with st.spinner("Fetching videos from playlist..."):
                video_details = get_playlist_video_urls(playlist_id)

            if not video_details:
                st.warning(
                    f"No videos found in playlist {playlist_id} or an error occurred during fetching."
                )
            else:
                results_df = pd.DataFrame(
                    columns=["Video Title", "Video URL", "Summary"]
                )
                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, detail in enumerate(video_details):
                    video_title = detail["title"]
                    video_url = detail["url"]

                    status_text.text(
                        f"Processing video {i+1}/{len(video_details)}: {video_title}"
                    )

                    # Summarize using URL
                    with st.spinner(f"Summarizing '{video_title}'..."):
                        summary = summarize_text_with_gemini(video_url)

                    new_row = pd.DataFrame(
                        [
                            {
                                "Video Title": video_title,
                                "Video URL": video_url,
                                "Summary": summary,
                            }
                        ]
                    )
                    results_df = pd.concat([results_df, new_row], ignore_index=True)

                    progress_bar.progress((i + 1) / len(video_details))

                st.success("Summarization complete!")
                st.dataframe(results_df, height=300, use_container_width=True)

                csv = results_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="Download Summaries as CSV",
                    data=csv,
                    file_name="playlist_summaries.csv",
                    mime="text/csv",
                )