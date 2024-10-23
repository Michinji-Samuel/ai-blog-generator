from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
# from pytube import YouTube
import os
import assemblyai as aai
import openai
from .models import BlogPost
import os
from yt_dlp import YoutubeDL
import logging
from dotenv import load_dotenv


load_dotenv()


# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

# @csrf_exempt
# def generate_blog(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             yt_link = data['link']
#         except (KeyError, json.JSONDecodeError):
#             return JsonResponse({'error': 'Invalid data sent'}, status=400)


#         # get yt title
#         title = yt_title(yt_link)

#         # get transcript
#         transcription = get_transcription(yt_link)
#         if not transcription:
#             return JsonResponse({'error': " Failed to get transcript"}, status=500)


#         # use OpenAI to generate the blog
#         blog_content = generate_blog_from_transcription(transcription)
#         if not blog_content:
#             return JsonResponse({'error': " Failed to generate blog article"}, status=500)

#         # save blog article to database
#         new_blog_article = BlogPost.objects.create(
#             user=request.user,
#             youtube_title=title,
#             youtube_link=yt_link,
#             generated_content=blog_content,
#         )
#         new_blog_article.save()

#         # return blog article as a response
#         return JsonResponse({'content': blog_content})
#     else:
#         return JsonResponse({'error': 'Invalid request method'}, status=405)

# Configure logging
logger = logging.getLogger(__name__)

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            # Load data from request
            data = json.loads(request.body)
            yt_link = data['link']
            logger.info(f"Received YouTube link: {yt_link}")

            # Get YouTube title
            title = yt_title(yt_link)
            logger.info(f"Video Title: {title}")

            # Get transcript
            transcription = get_transcription(yt_link)
            if not transcription:
                logger.error("Failed to get transcription.")
                return JsonResponse({'error': 'Failed to get transcript'}, status=500)

            logger.info(f"Transcription obtained: {transcription}")

            # Generate blog content from transcription
            blog_content = generate_blog_from_transcription(transcription)
            if not blog_content:
                logger.error("Failed to generate blog article.")
                return JsonResponse({'error': 'Failed to generate blog article'}, status=500)

            # Save the new blog article to the database
            new_blog_article = BlogPost.objects.create(
                user=request.user,
                youtube_title=title,
                youtube_link=yt_link,
                generated_content=blog_content,
            )
            new_blog_article.save()

            logger.info("Blog article created successfully.")

            # Return the generated blog content in the response
            return JsonResponse({'content': blog_content})

        except json.JSONDecodeError:
            logger.error("Invalid JSON data received.")
            return JsonResponse({'error': 'Invalid data sent'}, status=400)
        except KeyError as e:
            logger.error(f"Missing key in request data: {str(e)}")
            return JsonResponse({'error': 'Missing key in request data'}, status=400)
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)

    else:
        logger.error("Invalid request method.")
        return JsonResponse({'error': 'Invalid request method'}, status=405)

# def yt_title(link):
#     yt = YouTube(link)
#     title = yt.title
#     return title

def yt_title(link):
    with YoutubeDL() as ydl:
        info = ydl.extract_info(link, download=False)  # Set download to False to get info only
        return info.get('title', 'No Title Found')  # Return the title or a default message

# def download_audio(link):
#     yt = YouTube(link)
#     video = yt.streams.filter(only_audio=True).first()
#     out_file = video.download(output_path=settings.MEDIA_ROOT)
#     base, ext = os.path.splitext(out_file)
#     new_file = base + '.mp3'
#     os.rename(out_file, new_file)
#     return new_file

def download_audio(link):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(settings.MEDIA_ROOT, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'ffmpeg_location': r'C:\ffmpeg-N-117624-g9eb7e8d2a4-win64-gpl\bin',  #Ensure this is the correct path
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            new_file = os.path.join(settings.MEDIA_ROOT, f"{info['title']}.mp3")
            return new_file
    except Exception as e:
        print(f"Error downloading audio: {str(e)}")  # Log the error for debugging
        return None


# def get_transcription(link):
#     audio_file = download_audio(link)
#     aai.settings.api_key = "your-assemblyai-api-key"

#     transcriber = aai.Transcriber()
#     transcript = transcriber.transcribe(audio_file)

#     return transcript.text


def get_transcription(link):
    try:
        # Download the audio file using yt-dlp
        audio_file = download_audio(link)

        # Ensure the AssemblyAI API key is set
        aai.settings.api_key = os.getenv('assembly_api')
        if not aai.settings.api_key:
            logging.error("AssemblyAI API key is missing.")
            return None

        # Initialize the transcriber
        transcriber = aai.Transcriber()

        # Perform the transcription
        logging.info(f"Transcribing audio file: {audio_file}")
        transcript = transcriber.transcribe(audio_file)

        if transcript:
            logging.info(f"Transcription successful: {transcript.text[:100]}")  # Log first 100 characters
            return transcript.text
        else:
            logging.error("No transcription result.")
            return None

    except Exception as e:
        logging.error(f"Failed to get transcription: {e}")
        return None


def generate_blog_from_transcription(transcription):
    openai.settings.api_key = os.getenv('openai_api')  # Replace with your actual OpenAI API key

    prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, but don't make it look like a YouTube video. Make it look like a proper blog article:\n\n{transcription}\n\nArticle:"

    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",  # You can also use "gpt-4" if you have access
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=1000
    )

    generated_content = response.choices[0].message['content'].strip()

    return generated_content


def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})
        
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message':error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message':error_message})
        
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')