# Getting Set Up

The steps below should help you get set up virtualenv and pre-commit on an Ubuntu system.

```bash
# install python 3 and dependencies
sudo apt update
sudo apt install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    pre-commit \
    python3 \
    python-dev \
    python3-pip \
    python3-venv

# set up pre-commit so basic linting happens before every commit
pre-commit install
pre-commit run --all-files
```

The steps below should help you get set up the tool on an Ubuntu system.

```shell
# set up virtualenv
python -m venv '.venv'
source .venv/bin/activate

# install requirements
pip install -r requirements.txt
```

Install Java as a prerequisite for installing Audiveris.
NOTE: This may not be required anymore as of Audiveris 5.5. Need to validate.

```shell
sudo apt update
apt search openjdk | grep -E "openjdk-[0-9]+-jdk"
sudo apt install openjdk-17-jdk -y
java -version
```

Install Audiveris to generate .musicxml files from a PDF sheet music.

```shell
# https://github.com/Audiveris/audiveris/releases/tag/5.7.1
_version="5.7.1"
_file="Audiveris-${_version}-ubuntu24.04-x86_64.deb"
_download_dir="/tmp"
wget -O "${_download_dir}/${_file}" "https://github.com/Audiveris/audiveris/releases/download/${_version}/${_file}"
sudo apt install "${_download_dir}/${_file}"
sudo ln -s /opt/audiveris/bin/Audiveris /usr/local/bin/audiveris
```

Install Lilypond and MuseScore to generate PDF sheet music based on .musicxml files.

```shell
sudo apt install -y lilypond
which lilypond
lilypond --version

sudo apt install -y musescore
which musescore
musescore --version
```

Note: If you're using Docker, the provided image already includes MuseScore and LilyPond. You can skip local installation and run:

```shell
docker compose build
docker compose up -d
docker compose run --rm piano-learning python3 main.py convert_musicxml_to_pdf user/input/Your_Score.musicxml --convert-with-musescore --overwrite
```

OpenAI credentials are only required for commands that use `--simplifier openai`.
If you are only using the default `music21` simplifier, converting PDFs, analyzing scores, or rendering PDFs, you can skip this step.

```shell
cat > .env <<'EOF'
OPENAI_API_KEY=INSERT_KEY_HERE
# Optional model overrides:
# OPENAI_MODEL=gpt-5.5
# OPENAI_AGENT_MODEL=gpt-5.5
EOF
```

Useful isolated checks after setup:

```shell
# does not require OPENAI_API_KEY
python main.py generate_simplified_musicxml user/input/Your_Score.musicxml

# requires OPENAI_API_KEY
python main.py generate_simplified_musicxml user/input/Your_Score.musicxml --simplifier openai

# prompt generation only; requires --simplifier openai but does not call the API
python main.py generate_simplified_musicxml user/input/Your_Score.musicxml --simplifier openai --manual
```

## Recurring

To deactivate or reactivate your virtual environment, simply run:

```shell
deactivate                # deactivates virtualenv
source .venv/bin/activate # reactivates virtualenv
```
