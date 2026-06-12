import os
import subprocess
import time
import json
import imageio_ffmpeg
from gtts import gTTS
from playwright.sync_api import sync_playwright

# Use imageio_ffmpeg to get duration
def get_duration(filename):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run([
        ffmpeg_exe, "-i", filename
    ], stderr=subprocess.PIPE, text=True)

    # Extract duration from stderr
    for line in result.stderr.split('\n'):
        if 'Duration' in line:
            # line looks like: "  Duration: 00:00:10.50, start: 0.000000, bitrate: 64 kb/s"
            parts = line.split(',')
            duration_str = parts[0].split('Duration:')[1].strip()
            # 00:00:10.50
            h, m, s = duration_str.split(':')
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0

def generate_narration():
    scenarios = {
        "intro": "Welcome to the FitFindr demo. We will walk through three scenarios to demonstrate the power of our AI personal stylist.",
        "scenario1": "In our first scenario, we explore the happy path workflow. The user is looking for red jeans from a status symbol brand. They enter the query: 'gimme red jeans with most status symbol type of brand' and set the User ID to 'default_user'. As the agent processes this, it first triggers the 'search_listings' tool. It scans our database and successfully retrieves a pair of Vintage Levi's 501s, which are then saved into the session state. Next, this data is passed to the 'suggest_outfit' tool, which combines the jeans with the user's existing wardrobe to create a cohesive look. Finally, the 'create_fit_card' tool generates a trendy social media caption. In summary, the agent took the Levi's 501s and successfully constructed a vintage streetwear outfit card pairing it with a ribbed tank top, a black denim jacket, and a tailored social media caption ready for export.",
        "scenario2": "Scenario two focuses on our upgraded Price Fairness feature. We're going to isolate and evaluate the price of those Levi's jeans we just found. Our custom refactored logic in tools.py starts by extracting the fine-grained clothing noun—in this case, 'jeans'. It then applies a 20% to 300% median outlier filter to ensure data accuracy. The agent verifies the Tier 1 brand premium count and sets a reliable baseline price. The final analysis clearly outlines that while the item carries a premium brand status, the current listing price runs slightly higher than the clean market median, giving the user transparent data for their purchasing decision.",
        "scenario3": "Finally, scenario three demonstrates a triggered graceful failure. The user enters a highly constrained query: 'designer ballgown size XXS under $5'. Watch as the agent pipeline handles this severe constraint. The search returns an empty list, and our planning loop intelligently detects this. Instead of passing corrupt or empty state to the styling tools, the loop conditionally terminates execution early. To conclude our demonstration, this scenario confirms that when zero marketplace listings match user criteria, the agent gracefully drops out of the loop and populates an actionable notification instructing the user to loosen their search filters rather than crashing the interface or rendering blank panels.",
        "outro": "This concludes our FitFindr demonstration. Thank you for watching!"
    }

    os.makedirs("demo_assets/audio", exist_ok=True)
    durations = {}
    audio_paths = ["intro", "scenario1", "scenario2", "scenario3", "outro"]

    for name in audio_paths:
        text = scenarios[name]
        path = f"demo_assets/audio/{name}.mp3"
        print(f"Generating {path}...")
        tts = gTTS(text=text, lang='en')
        tts.save(path)
        durations[name] = get_duration(path)

    # Concatenate audio
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    with open("audio_list.txt", "w") as f:
        for name in audio_paths:
            f.write(f"file 'demo_assets/audio/{name}.mp3'\n")

    subprocess.run([
        ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", "audio_list.txt",
        "-c", "copy", "demo_assets/audio/full_narration.mp3"
    ], check=True)
    os.remove("audio_list.txt")

    return durations

def record_browser(durations):
    print("Starting Gradio app...")
    # Enable debug panel for demo
    my_env = os.environ.copy()
    my_env["FITFINDR_DEBUG"] = "true"
    proc = subprocess.Popen(["python", "app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=my_env)
    time.sleep(10)

    os.makedirs("demo_assets/videos", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 1600},
            record_video_dir="demo_assets/videos"
        )
        page = context.new_page()

        try:
            print("Navigating to app...")
            page.goto("http://localhost:7860")

            # INTRO
            print(f"Intro: waiting {durations['intro']}s")
            page.wait_for_timeout(durations['intro'] * 1000)

            # SCENARIO 1
            print(f"Scenario 1: total duration {durations['scenario1']}s")
            start_time = time.time()
            page.get_by_label("What are you looking for?").fill("gimme red jeans with most status symbol type of brand")
            page.get_by_label("User ID").fill("default_user")
            page.wait_for_timeout(2000)
            page.get_by_role("button", name="Find it").click()
            page.wait_for_selector("text=Levi's", timeout=60000)

            elapsed = time.time() - start_time
            remaining = (durations['scenario1'] - elapsed)
            if remaining > 0:
                print(f"Scenario 1: remaining wait {remaining}s")
                page.wait_for_timeout(remaining * 1000)

            # SCENARIO 2
            print(f"Scenario 2: waiting {durations['scenario2']}s")
            page.evaluate("window.scrollTo(0, 600)")
            page.wait_for_timeout(durations['scenario2'] * 1000)

            # SCENARIO 3
            print(f"Scenario 3: total duration {durations['scenario3']}s")
            start_time = time.time()
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(2000)
            page.get_by_label("What are you looking for?").fill("designer ballgown size XXS under $5")
            page.wait_for_timeout(2000)
            page.get_by_role("button", name="Find it").click()
            page.wait_for_selector("text=No results found", timeout=60000)

            elapsed = time.time() - start_time
            remaining = (durations['scenario3'] - elapsed)
            if remaining > 0:
                print(f"Scenario 3: remaining wait {remaining}s")
                page.wait_for_timeout(remaining * 1000)

            # OUTRO & DEBUG PANEL
            print(f"Outro: waiting {durations['outro']}s")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(durations['outro'] * 1000)

            # Final buffer
            page.wait_for_timeout(2000)

        finally:
            context.close()
            browser.close()
            proc.terminate()

def merge_video():
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    video_dir = "demo_assets/videos"
    video_files = [os.path.join(video_dir, f) for f in os.listdir(video_dir) if f.endswith(".webm")]
    latest_video = max(video_files, key=os.path.getctime)

    print(f"Merging {latest_video} with narration...")
    # Use -shortest to ensure they match if video is slightly longer
    # or pad with silence/static frame if video is shorter (though we handled that with timeouts)
    subprocess.run([
        ffmpeg_exe, "-y", "-i", latest_video, "-i", "demo_assets/audio/full_narration.mp3",
        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "fitfindr_demo.mp4"
    ], check=True)

if __name__ == "__main__":
    durations = generate_narration()
    print(f"Narrations generated: {json.dumps(durations, indent=2)}")
    record_browser(durations)
    merge_video()
    print("Done! Video saved as fitfindr_demo.mp4")
