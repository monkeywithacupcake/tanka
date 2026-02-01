# 🐦 Tanka
**Enhanced data collection and analysis for HaikuBox**

I got a HaikuBox, and I think it is pretty neat. It uses BirdNet to match sounds with bird calls and songs and gives you a glimpse into birds around you. It even has an API. However, the API only gives you a summary. If you want to be able to do more analysis, like look at time of day or other aspects of its findings, you have to go to the website and manually download your data. 

Like the tanka poetry form that extends haiku with deeper reflection, Tanka extends HaikuBox data by allowing automated collecting of the detailed data. Download detailed detection CSVs, track patterns over time, and discover birds that visit your backyard—data and features not available through the standard HaikuBox interface.

## Setup

### 1. Prerequisites
- Python 3.8 or higher
- A HaikuBox account at listen.haikubox.com

### 2. Installation

```bash
# Clone or download the project
cd tanka

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install firefox
```

### 3. Configuration

Edit [config/haikuboxes.yaml](config/haikuboxes.yaml) and add your credentials:

```yaml
haikuboxes:
  - name: your-haikubox-name  # Replace with your HaikuBox name
    enabled: true

settings:
  download_dir: ./downloads
  headless: true  # Set to false to see browser during download
  download_timeout: 60
  log_level: INFO

  # Authentication credentials for listen.haikubox.com
  auth:
    email: "your.email@example.com"  # Your HaikuBox login email
    password: "your_password"  # Your HaikuBox login password
  # Bluesky settings: to make posting work
  # you should go make an app password do not use your regular one
  bsky:
    user_name: "user_name.bsky.social" # Your Bluesky User Name
    app_pword: "app_password" # Your App Password for This
  # Analysis settings (optional - these are the defaults)
  analysis:
    score_threshold: 0.5  # Minimum confidence (0.0 to 1.0)
    top_n: 10  # Number of top species to show
    exclude_species: []  # List of species to exclude, e.g., ["House Sparrow", "Rock Pigeon"]
```

**IMPORTANT:** Keep [config/haikuboxes.yaml](config/haikuboxes.yaml) secure as it contains your credentials. Add it to `.gitignore` if using version control.

## Usage

I have more ideas later, but for now, this repo has code to download data and to do some simple analysis.
It also can post to bluesky.

### Expected use

Typical expected use is: download data (dates yesterday and today, if you are behind UTC), analyze data (date yesterday, default), post analysis (yesterday, default)

Assuming it is 2026-02-01, so you want to post about Jan 31: 

```bash
python3 download.py --dates 2026-01-31-2026-02-01
python3 analyze.py --time --save
python3 bsky_post.py 
```

This is now default behavior of `python main.py`!

**I plan to make this so that main will do all of this and move the main actions to download. **

### Downloading Bird Data (download.py)

**Download yesterday's data** (the most common use case):
```bash
python3 download.py
```

**Download a specific date:**
```bash
python3 download.py --date 2026-01-15
```

**Download a date range:**
This actually downloads each day in this range individually, but can save you time if you are trying to build your history.
```bash
python3 download.py --dates 2026-01-10-2026-01-15
```

**Download for a specific HaikuBox only:**
I only have one, but you might have more than one. TBH - i can't really test this one.
```bash
python3 download.py --box your-haikubox-name
```

**Run with visible browser** (great for debugging):
If something is not right (the date picker is a beast, for example), you can see what is happening with this. 
```bash
python3 download.py --headless false
```

### Analyzing Bird Data (analyze.py)

Once you have CSV files downloaded, use the analyzer to get some simple insights.
(I'm working on some other ones, but releasing with this simple summary)

**Analyze yesterday's data** (default):
```bash
python3 analyze.py
```

**Analyze a specific date:**
```bash
python3 analyze.py --date 2026-01-20
```

**Analyze a specific HaikuBox:**
```bash
python3 analyze.py --box your-haikubox-name
```

**Analyze all downloaded data:**
I broke this by adding the save option, it still 'works' but i need to rewrite it 
--all should return a different result, something that makes sense across dates

```bash
python3 analyze.py --all
```

**Customize analysis parameters:**
```bash
# Set confidence threshold (0.0 to 1.0)
# the default is 0.5
python3 analyze.py --threshold 0.7

# Change number of top species shown
# the default is 10
python3 analyze.py --top 15
```

**Example output:**
```
Bird Detection Summary: my-haiku-brbs_2026-01-01.csv
============================================================
Total detections: 566
Above threshold (0.5): 380
Unique species: 18

New/Rare Birds (not seen in last 7 days):
------------------------------------------------------------
  * Canada Jay
  * Pine Siskin
  * White-throated Sparrow

Top 10 Species:
------------------------------------------------------------
 1. Anna's Hummingbird              227 detections
 2. Golden-crowned Kinglet          115 detections
 3. Chestnut-backed Chickadee        96 detections
 4. Brown Creeper                    70 detections
 5. Red-breasted Nuthatch            61 detections
...
```

### Post the Birds to Bluesky

```bash
./venv/bin/python bsky_post.py 
```

Do a dry run first to see what will post

```bash
./venv/bin/python bsky_post.py --dryrun
```

### ⏰ Automated Daily Downloads & Analysis

Set up cron to automatically download yesterday's data every night and optionally analyze it. This is the way to go.

#### Step 1: Get your project path

```bash
cd tanka
pwd  # Copy this path for the next step
```

#### Step 2: Test the scripts

You can skip this if you already know it works

```bash
# Test download
python3 download.py

# Test analysis
python3 analyze.py
```

#### Step 3: Set up cron job

```bash
crontab -e  # Opens cron editor
```

**Option A: Download only** (at 2:00 AM daily):
```bash
0 2 * * * cd /path/to/tanka && ./venv/bin/python download.py >> logs/cron.log 2>&1
```

**Option B: Download + Analyze** (download at 2:00 AM, analyze at 2:05 AM):
```bash
0 2 * * * cd /path/to/tanka && ./venv/bin/python download.py >> logs/cron.log 2>&1
5 2 * * * cd /path/to/tanka && ./venv/bin/python analyze.py >> logs/cron.log 2>&1
```

💡 **Cron time format:** `minute hour day month day_of_week command`

NOTE **macOS-specific:**
You might have to Grant Terminal Full Disk Access
   - System Preferences → Privacy & Security → Full Disk Access
   - Add Terminal (or your terminal app) to the list

## Project Structure

```
tanka/
├── src/
│   ├── __init__.py
│   ├── config.py          # Configuration handling
│   ├── downloader.py      # Playwright browser automation for downloads
│   ├── analyzer.py        # Bird data analysis and statistics
│   └── logger.py          # Logging setup
│   └── poster.py          # Posts to bluesky
├── config/
│   └── haikuboxes.yaml    # HaikuBox and authentication config
├── analysis/              # Saved analysis JSON (created automatically)
├── downloads/             # Downloaded CSV files (created automatically)
├── logs/                  # Application logs
├── download.py                # Download script - run this to get data
├── analyze.py             # Analysis script - run this to analyze data
├── bsky_post.py           # Posting script - run this to post to bsky
├── requirements.txt       # Python dependencies
└── README.md              # This file
```


## Logs

Logs are saved to [logs/haikubox_YYYYMMDD.log](logs/) with daily rotation.
They will be deleted after 7 days by default.

To view recent logs:
```bash
tail -f logs/haikubox_*.log
```

## Adding More HaikuBoxes

Edit [config/haikuboxes.yaml](config/haikuboxes.yaml) and add additional boxes:

```yaml
haikuboxes:
  - name: first-haikubox
    enabled: true
  - name: second-haikubox
    enabled: true
  - name: disabled-box
    enabled: false  # This one won't be processed
```

## 📁 Downloaded Files

CSV files are saved as: `{haikubox_name}_{YYYY-MM-DD}.csv`



## About the Name

**Tanka** (短歌) is a classical Japanese poetry form that extends the haiku structure. While haiku captures a moment in three lines (5-7-5 syllables), tanka adds two more lines (7-7 syllables) to provide deeper reflection and context.

Just as tanka poetry offers "more" than haiku, Tanka gives you more data and insights than the standard HaikuBox interface:
- Individual detection CSVs (not available via web interface)
- Historical pattern tracking
- Rare bird detection
- Customizable analysis
