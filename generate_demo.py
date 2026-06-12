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
    # Exact text track with all "red jeans"/"jeans"/"Levi's" references swapped to "vintage denim jacket"/"jacket"/"Wrangler"
    scenarios = {
        "intro_s1": (
            "Welcome to the FitFindr agent demonstration. We are executing our multi-tool pipeline to fulfill the Project 2 engineering requirements. "
            "In Scenario One, we execute the Happy Path workflow. Our user enters a natural language query seeking a vintage denim jacket with a status symbol type of brand. "
            "The core planning loop intercepts this input and programmatically triggers our first tool, search listings. It scans our marketplace database and returns a dictionary matching a Vintage Wrangler Denim Jacket. "
            "Without any manual user re-entry, this data object is committed to our central session state. The agent passes this data directly to our second tool, suggest outfit, which cross-references the user's saved wardrobe to construct a cohesive streetwear look. "
            "Finally, that outfit recommendation flows automatically into our third tool, create fit card, which returns a tailored, shareable social media caption. "
            "In summary, the agent took the Wrangler jacket and successfully constructed a vintage streetwear outfit card pairing it with a ribbed tank top, a black denim jacket, and a tailored social media caption ready for export."
        ),
        "s2": (
            "In Scenario Two, we evaluate our custom Price Fairness stretch feature. We're going to isolate and evaluate the price of that Wrangler jacket we just found. "
            "Our refactored logic in tools.py optimizes the evaluation by isolating the specific product noun, 'jacket'. "
            "It filters out extreme pricing anomalies using a clean twenty-to-three-hundred percent market median outlier mask, checks for Tier One brand premium counts, and returns a transparent e-commerce value assessment "
            "showing that while this item carries a brand premium, it sits slightly above the marketplace average."
        ),
        "s3": (
            "Finally, in Scenario Three, we demonstrate our adaptive planning loop's graceful failure path. When handed a highly constrained query like a designer ballgown under five dollars, our search listings tool returns an empty list. "
            "The planning loop detects this state change immediately and alters its execution path—terminating early to prevent crashing or passing empty parameters downstream, and writing an actionable error notification instructing the consumer how to loosen their search filters."
        )
    }

    os.makedirs("demo_assets/audio", exist_ok=True)
    durations = {}
    audio_paths = ["intro_s1", "s2", "s3"]

    # Write transcript
    with open("DEMO_TRANSCRIPT.md", "w") as f:
        f.write("# FitFindr Demo Transcript\n\n")
        f.write("## Introduction & Scenario 1: Happy Path Workflow\n")
        f.write(scenarios["intro_s1"] + "\n\n")
        f.write("## Scenario 2: Price Fairness Evaluation\n")
        f.write(scenarios["s2"] + "\n\n")
        f.write("## Scenario 3: Graceful Failure Path\n")
        f.write(scenarios["s3"] + "\n")

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
    # Kill any existing app.py processes
    subprocess.run("pkill -f app.py", shell=True)
    proc = subprocess.Popen(["python", "app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=my_env)
    time.sleep(10)

    os.makedirs("demo_assets/videos", exist_ok=True)

    with sync_playwright() as p:
        # Launch with clear text flags
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-font-subpixel-positioning']
        )
        # Retina emulation
        context = browser.new_context(
            viewport={'width': 1280, 'height': 1600},
            device_scale_factor=2,
            record_video_dir="demo_assets/videos",
            record_video_size={'width': 1280, 'height': 1600}
        )
        page = context.new_page()

        try:
            print("Navigating to app...")
            page.goto("http://localhost:7860")

            # SCENARIO 1
            print(f"Scenario 1: total duration {durations['intro_s1']}s")
            start_time = time.time()

            page.get_by_label("What are you looking for?").fill("gimme a vintage denim jacket with most status symbol type of brand")
            page.get_by_label("User ID").fill("default_user")
            page.wait_for_timeout(2000)
            page.get_by_role("button", name="Find it").click()
            page.wait_for_selector("text=Wrangler", timeout=60000)

            elapsed = time.time() - start_time
            remaining = (durations['intro_s1'] - elapsed)
            if remaining > 0:
                print(f"Scenario 1: remaining wait {remaining}s")
                page.wait_for_timeout(remaining * 1000)

            # SCENARIO 2
            print(f"Scenario 2: total duration {durations['s2']}s")
            start_time = time.time()

            # Re-run with specific query
            page.evaluate("window.scrollTo(0, 0)")
            page.get_by_label("What are you looking for?").fill("vintage denim jacket")
            page.wait_for_timeout(1000)
            page.get_by_role("button", name="Find it").click()
            page.wait_for_selector("text=Wrangler", timeout=60000)

            # Scroll to Price Analysis
            page.evaluate("window.scrollTo(0, 600)")

            elapsed = time.time() - start_time
            remaining = (durations['s2'] - elapsed)
            if remaining > 0:
                print(f"Scenario 2: remaining wait {remaining}s")
                page.wait_for_timeout(remaining * 1000)

            # SCENARIO 3
            print(f"Scenario 3: total duration {durations['s3']}s")
            start_time = time.time()

            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)
            page.get_by_label("What are you looking for?").fill("designer ballgown size XXS under $5")
            page.wait_for_timeout(1000)
            page.get_by_role("button", name="Find it").click()
            page.wait_for_selector("text=No results found", timeout=60000)

            # Scroll to Debug Panel
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            elapsed = time.time() - start_time
            remaining = (durations['s3'] - elapsed)
            if remaining > 0:
                print(f"Scenario 3: remaining wait {remaining}s")
                page.wait_for_timeout(remaining * 1000)

            # Final buffer
            page.wait_for_timeout(3000)

        finally:
            context.close()
            browser.close()
            proc.terminate()

def merge_video():
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    video_dir = "demo_assets/videos"
    video_files = [os.path.join(video_dir, f) for f in os.listdir(video_dir) if f.endswith(".webm")]
    if not video_files:
        print("No video files found!")
        return
    latest_video = max(video_files, key=os.path.getctime)

    print(f"Merging {latest_video} with narration...")
    # Use -shortest to ensure they match
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
    print("Done! Video saved as fitfindr_demo.mp4 and transcript as DEMO_TRANSCRIPT.md")
