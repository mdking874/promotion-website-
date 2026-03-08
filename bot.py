import os
import requests
import re
import uuid
import time
import concurrent.futures
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, make_response
from urllib.parse import urljoin
import json

app = Flask(__name__)

# ⚠️ ১. এখানে আপনার ওয়েবসাইটগুলোর লিংক ক্যাটাগরি অনুযায়ী দিন
TARGET_CATEGORIES = {
    "Indian":[
        "https://indian-site1.com",
        "https://indian-site2.com"
    ],
    "Bangla":[
        "https://bangla-site1.com"
    ],
    "Pakistani":[
        "https://pakistani-site1.com"
    ]
}

# ✅ ২. আপনার ফায়ারবেস ডাটাবেসের লিংক
FIREBASE_URL = "https://bkhot-5f82a-default-rtdb.firebaseio.com/videos.json"

def get_stream_link(page_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(page_url, headers=headers, timeout=5)
        content = res.text
        m3u8 = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', content)
        if m3u8: return m3u8[0]
        mp4 = re.findall(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', content)
        if mp4: return mp4[0]
        return None
    except:
        return None

def scrape_single_site(data):
    category, site = data
    site_links =[]
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(site, headers=headers, timeout=8)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for a in soup.find_all('a'):
            img = a.find('img')
            page_link = a.get('href')
            
            if img and page_link:
                full_page_link = urljoin(site, page_link)
                thumb = img.get('data-src') or img.get('data-lazy-src') or img.get('data-original') or img.get('src') or img.get('poster')
                title = img.get('alt') or img.get('title') or a.text.strip() or "New Video"
                
                if thumb and not thumb.startswith('data:image'):
                    if thumb.startswith('//'): thumb = "https:" + thumb
                    elif thumb.startswith('/'): thumb = urljoin(site, thumb)
                    
                    if not any(v['page_link'] == full_page_link for v in site_links):
                        site_links.append({
                            'page_link': full_page_link,
                            'thumb': thumb,
                            'title': title,
                            'category': category 
                        })
    except Exception as e:
        pass
    return site_links[:5]

def process_video_link(item):
    stream_url = get_stream_link(item['page_link'])
    if stream_url:
        return {
            "id": str(uuid.uuid4())[:8],
            "title": item['title'],
            "thumb": item['thumb'],
            "url": stream_url,
            "category": item['category'] 
        }
    return None

def fetch_videos_now():
    TARGET_LIST =[]
    for cat, urls in TARGET_CATEGORIES.items():
        for url in urls:
            TARGET_LIST.append((cat, url))
            
    all_valid_links = []
    videos =[]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(scrape_single_site, TARGET_LIST)
        for res in results:
            all_valid_links.extend(res)
            
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        video_results = executor.map(process_video_link, all_valid_links)
        for v in video_results:
            if v:
                videos.append(v)
    return videos

def get_firebase_videos():
    try:
        res = requests.get(FIREBASE_URL)
        if res.status_code == 200 and res.json():
            return res.json()
    except:
        pass
    return[]

def save_firebase_videos(videos_list):
    try:
        requests.put(FIREBASE_URL, json=videos_list)
    except:
        pass

# ==========================================
# 🌟 মেইন ওয়েবসাইটের HTML (ভিডিও হাব)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 Auto Video Hub</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>.line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }</style>
</head>
<body class="bg-gray-900 text-white font-sans">
    <nav class="bg-gray-800 p-3 shadow-lg flex justify-between items-center z-50">
        <a href="/" class="text-xl font-bold text-indigo-500 flex items-center gap-2">🎬 Auto Video Hub</a>
        <div class="text-xs text-indigo-200 font-bold bg-indigo-900 px-3 py-1.5 rounded-full border border-indigo-500 shadow-lg">☁️ Saved Videos: {{ total_count }}</div>
    </nav>

    <div class="bg-gray-800 p-3 flex gap-2 overflow-x-auto justify-center border-b border-gray-700 text-sm shadow-inner sticky top-0 z-40">
        <a href="/" class="px-4 py-1.5 rounded-full text-white font-bold transition whitespace-nowrap {% if active_cat == 'Home' %}bg-indigo-600 shadow-md{% else %}bg-gray-700 hover:bg-gray-600{% endif %}">🏠 All Videos</a>
        <a href="/category/Indian" class="px-4 py-1.5 rounded-full text-white font-bold transition whitespace-nowrap {% if active_cat == 'Indian' %}bg-indigo-600 shadow-md{% else %}bg-gray-700 hover:bg-gray-600{% endif %}">🇮🇳 Indian</a>
        <a href="/category/Bangla" class="px-4 py-1.5 rounded-full text-white font-bold transition whitespace-nowrap {% if active_cat == 'Bangla' %}bg-indigo-600 shadow-md{% else %}bg-gray-700 hover:bg-gray-600{% endif %}">🇧🇩 Bangla</a>
        <a href="/category/Pakistani" class="px-4 py-1.5 rounded-full text-white font-bold transition whitespace-nowrap {% if active_cat == 'Pakistani' %}bg-indigo-600 shadow-md{% else %}bg-gray-700 hover:bg-gray-600{% endif %}">🇵🇰 Pakistani</a>
    </div>

    {% if current_video %}
    <div class="container mx-auto p-2 sm:p-4 max-w-4xl mt-2 block">
        <button onclick="history.back()" class="inline-block mb-4 bg-gray-700 text-white px-3 py-1.5 rounded text-sm font-bold shadow">🔙 ফিরে যান</button>
        <div class="bg-black rounded-lg overflow-hidden shadow-2xl relative border border-gray-800">
            <video id="main-player" controls autoplay class="w-full aspect-video" controlsList="nodownload"></video>
        </div>
        <div class="bg-gray-800 p-4 mt-4 rounded-lg shadow-lg border border-gray-700">
            <h1 class="text-lg sm:text-xl font-bold text-white mb-2">{{ current_video.title }}</h1>
            <span class="inline-block bg-indigo-600 text-xs px-2 py-1 rounded-full font-bold">🏷️ Category: {{ current_video.category | default('Mixed') }}</span>
        </div>
    </div>
    <script>
        var url = "{{ current_video.url }}";
        var player = document.getElementById('main-player');
        if (url.includes('.m3u8')) {
            if (Hls.isSupported()) {
                var hls = new Hls(); hls.loadSource(url); hls.attachMedia(player);
                hls.on(Hls.Events.MANIFEST_PARSED, function() { player.play(); });
            } else if (player.canPlayType('application/vnd.apple.mpegurl')) { player.src = url; player.play(); }
        } else { player.src = url; player.play(); }
    </script>
    {% else %}
    <div class="container mx-auto p-4 block">
        <h2 class="text-lg font-bold mb-4 border-b border-gray-700 pb-2 flex justify-between">
            🔥 {% if active_cat == 'Home' %}All Latest Videos{% else %}{{ active_cat }} Videos{% endif %}
        </h2>
        
        {% if videos %}
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 sm:gap-4">
            {% for video in videos %}
            <!-- লিংকে ক্লিক করলে আগে Verify পেজে যাবে -->
            <a href="/verify/{{ video.id }}" class="bg-gray-800 rounded-lg overflow-hidden shadow-md hover:shadow-xl transition border border-gray-700 group block relative">
                <div class="relative">
                    <img src="{{ video.thumb }}" loading="lazy" class="w-full h-28 sm:h-32 object-cover group-hover:opacity-75 transition bg-gray-700">
                    <div class="absolute bottom-1 right-1 bg-black bg-opacity-80 text-white text-[10px] px-1.5 py-0.5 rounded font-bold">▶ Play</div>
                    <div class="absolute top-1 left-1 bg-indigo-600 text-white text-[9px] px-1.5 py-0.5 rounded shadow-md font-bold uppercase">{{ video.category | default('Mixed') }}</div>
                </div>
                <div class="p-2.5">
                    <h3 class="font-semibold text-xs text-gray-200 line-clamp-2">{{ video.title }}</h3>
                </div>
            </a>
            {% endfor %}
        </div>
        {% else %}
        <p class="text-center text-gray-400 mt-10 animate-pulse">ভিডিও পাওয়া যায়নি বা আনা হচ্ছে... একটু অপেক্ষা করুন।</p>
        {% endif %}
    </div>
    {% endif %}
</body>
</html>
"""

# ==========================================
# 💰 আপনার Secure Link / Ad Page HTML
# ==========================================
LANDING_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Global Tech Solutions - Secure Link Portal</title>

    <!-- 🔴 Monetag Verification Code -->
    <meta name="monetag" content="আপনার_মোনেটাগ_ভেরিফিকেশন_কোড_এখানে">

    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">

    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { background: #f8f9fa; color: #2d3436; line-height: 1.6; }
        .navbar { background: #ffffff; padding: 15px 50px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); display: flex; justify-content: space-between; align-items: center; }
        .logo { font-size: 24px; font-weight: 700; color: #0984e3; letter-spacing: 1px; }
        .nav-links a { margin-left: 20px; text-decoration: none; color: #636e72; font-weight: 500; }
        .nav-links a:hover { color: #0984e3; }
        .hero-section { padding: 60px 20px; display: flex; justify-content: center; }
        .main-card { background: #ffffff; width: 100%; max-width: 650px; padding: 40px; border-radius: 16px; box-shadow: 0 15px 35px rgba(0, 0, 0, 0.08); text-align: center; border-top: 5px solid #0984e3; }
        .header-icon { width: 70px; height: 70px; background: #e0f7fa; color: #00acc1; border-radius: 50%; display: flex; justify-content: center; align-items: center; font-size: 32px; margin: 0 auto 20px auto; }
        .main-card h2 { font-size: 26px; color: #2d3436; margin-bottom: 10px; }
        .subtitle { font-size: 15px; color: #636e72; margin-bottom: 25px; }
        .ad-container { background: #f1f2f6; border: 2px dashed #ced6e0; border-radius: 10px; padding: 15px; margin: 20px 0; min-height: 250px; display: flex; align-items: center; justify-content: center; color: #a4b0be; font-size: 14px; }
        .progress-wrapper { background: #dfe4ea; border-radius: 20px; height: 12px; overflow: hidden; margin: 20px 0; }
        .progress-bar { background: linear-gradient(90deg, #0984e3, #00cec9); height: 100%; width: 0%; transition: width 1s linear; }
        .timer-text { font-size: 18px; font-weight: 600; color: #2d3436; margin-bottom: 20px; }
        .timer-text span { color: #d63031; font-size: 24px; }
        .action-btn { display: none; background: linear-gradient(135deg, #0984e3, #00cec9); color: #fff; border: none; padding: 16px 35px; font-size: 18px; font-weight: 600; border-radius: 30px; cursor: pointer; width: 100%; text-transform: uppercase; letter-spacing: 1px; box-shadow: 0 8px 20px rgba(9, 132, 227, 0.3); transition: 0.3s; }
        .action-btn:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(9, 132, 227, 0.5); }
        .articles-section { max-width: 1100px; margin: 0 auto 60px auto; padding: 0 20px; }
        .section-title { font-size: 28px; font-weight: 700; color: #2d3436; margin-bottom: 30px; text-align: center; }
        .article-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 30px; }
        .article-card { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 5px 15px rgba(0,0,0,0.05); transition: 0.3s; }
        .article-card:hover { transform: translateY(-5px); box-shadow: 0 10px 25px rgba(0,0,0,0.1); }
        .article-img { width: 100%; height: 180px; background: #dfe6e9; display: flex; align-items: center; justify-content: center; font-size: 40px; color: #b2bec3; }
        .article-content { padding: 25px; }
        .category { color: #0984e3; font-size: 12px; font-weight: 600; text-transform: uppercase; margin-bottom: 10px; display: block; }
        .article-title { font-size: 18px; font-weight: 700; color: #2d3436; margin-bottom: 15px; }
        .article-desc { font-size: 14px; color: #636e72; }
        .footer { background: #2d3436; color: #b2bec3; text-align: center; padding: 30px 20px; font-size: 14px; }
        .footer a { color: #00cec9; text-decoration: none; margin: 0 10px; }
        @media (max-width: 768px) { .nav-links { display: none; } .navbar { justify-content: center; } }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="logo">Global Tech Solutions</div>
        <div class="nav-links"><a href="#">Home</a><a href="#">Cloud Security</a><a href="#">Enterprise AI</a><a href="#">Contact</a></div>
    </nav>

    <section class="hero-section">
        <div class="main-card">
            <div class="header-icon">🛡️</div>
            <h2>Securing Your Connection</h2>
            <p class="subtitle">Our advanced servers are validating your request. Please wait.</p>

            <div class="ad-container">
                <!-- আপনার Monetag Banner Ad এর কোড এখানে বসাবেন -->[ Advertisement Space 1 ]
            </div>

            <div id="timer-section">
                <div class="timer-text">Validating link in <span id="time-left">15</span> seconds</div>
                <div class="progress-wrapper">
                    <div class="progress-bar" id="progress-bar"></div>
                </div>
            </div>

            <button id="go-button" class="action-btn" onclick="goToDestination()">🚀 Proceed to Destination</button>
            <p style="font-size: 12px; color: #a4b0be; margin-top: 15px;">Protected by Enterprise-Grade Encryption</p>
        </div>
    </section>

    <section class="articles-section">
        <h3 class="section-title">Latest Industry Insights</h3>
        <div class="article-grid">
            <div class="article-card"><div class="article-img">☁️</div><div class="article-content"><span class="category">Cloud Computing</span><h4 class="article-title">The Future of Multi-Cloud Architecture</h4></div></div>
            <div class="article-card"><div class="article-img">🔐</div><div class="article-content"><span class="category">Cybersecurity</span><h4 class="article-title">Zero Trust Security Protocols</h4></div></div>
            <div class="article-card"><div class="article-img">🤖</div><div class="article-content"><span class="category">Artificial Intelligence</span><h4 class="article-title">AI in Enterprise Workflows</h4></div></div>
        </div>
    </section>

    <script>
        const targetURL = "/watch/{{ video_id }}";
        
        let totalSeconds = 15;
        let currentSecond = 0;
        const timeDisplay = document.getElementById('time-left');
        const progressBar = document.getElementById('progress-bar');
        const timerSection = document.getElementById('timer-section');
        const goButton = document.getElementById('go-button');

        const interval = setInterval(() => {
            currentSecond++;
            timeDisplay.innerText = totalSeconds - currentSecond;
            progressBar.style.width = ((currentSecond / totalSeconds) * 100) + "%";
            if (currentSecond >= totalSeconds) {
                clearInterval(interval);
                timerSection.style.display = "none";
                goButton.style.display = "block";
                document.querySelector('h2').innerText = "Connection Secured!";
                document.querySelector('.subtitle').innerText = "Click the button below to access your video.";
            }
        }, 1000);

        function goToDestination() { window.location.href = targetURL; }
    </script>

    <!-- Push Notification Registration -->
    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', function() {
                navigator.serviceWorker.register('/sw.js').then(function(registration) {
                    console.log('SW registration successful.');
                }, function(err) {
                    console.log('SW registration failed: ', err);
                });
            });
        }
    </script>
</body>
</html>
"""

# ==========================================
# 🌐 Flask Routes 
# ==========================================

@app.route('/')
def home():
    all_videos = get_firebase_videos()
    if not isinstance(all_videos, list):
        all_videos =[]
    return render_template_string(HTML_TEMPLATE, videos=all_videos, current_video=None, total_count=len(all_videos), active_cat="Home")

@app.route('/category/<cat_name>')
def category(cat_name):
    all_videos = get_firebase_videos()
    if not isinstance(all_videos, list):
        all_videos =[]
    filtered_videos =[v for v in all_videos if v.get('category') == cat_name]
    return render_template_string(HTML_TEMPLATE, videos=filtered_videos, current_video=None, total_count=len(all_videos), active_cat=cat_name)

@app.route('/verify/<video_id>')
def verify_link(video_id):
    return render_template_string(LANDING_PAGE_TEMPLATE, video_id=video_id)

@app.route('/watch/<video_id>')
def watch(video_id):
    all_videos = get_firebase_videos()
    if not isinstance(all_videos, list):
        all_videos =[]
    video = next((v for v in all_videos if v['id'] == video_id), None)
    if video:
        return render_template_string(HTML_TEMPLATE, videos=None, current_video=video, total_count=len(all_videos), active_cat="Home")
    return "<body style='background:#111; color:white; text-align:center;'><h1 style='margin-top:50px;'>Video Not Found!</h1><a href='/' style='color:#6366f1;'>Go Home</a></body>", 404

# 🚀 Service Worker Route (Monetag Push Notification)
@app.route('/sw.js')
def service_worker():
    sw_code = """self.options = {
    "domain": "5gvci.com",
    "zoneId": 10699635
}
self.lary = ""
importScripts('https://5gvci.com/act/files/service-worker.min.js?r=sw')"""
    
    response = make_response(sw_code)
    response.headers['Content-Type'] = 'application/javascript'
    return response

# 🚀 Background Auto-Update Route
@app.route('/auto-update')
def auto_update():
    all_videos = get_firebase_videos()
    if not isinstance(all_videos, list):
        all_videos =[]
        
    new_videos = fetch_videos_now()
    existing_urls = set([v['url'] for v in all_videos])
    existing_titles = set([v['title'] for v in all_videos])
    added_count = 0
    
    for video in new_videos:
        if video['url'] not in existing_urls and video['title'] not in existing_titles:
            all_videos.insert(0, video)
            existing_urls.add(video['url'])
            existing_titles.add(video['title'])
            added_count += 1
            
    all_videos = all_videos[:1000] # স্টোরেজ লিমিট ১০০০ ভিডিও 
    
    if added_count > 0:
        save_firebase_videos(all_videos)
        return f"Success! Added {added_count} NEW videos to database."
    
    return "Checked! No new videos found right now. No duplicates added."

if __name__ == '__main__':
    app.run(debug=True)
