# Piano Learning

## Getting Set Up

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

Install Lilypond and Musescore to generate PDF sheet music based on .musicxml files.

```shell
sudo apt install -y lilypond
which lilypond
lilypond --version

sudo snap install musescore
snap list musescore
```

We need to set up our `.env` file with the required API keys.

```shell
cp .env.template .env
sed -i 's/OPENAI_API_KEY=.*/OPENAI_API_KEY=INSERT_KEY_HERE/g' .env
```

### Recurring

To deactivate or reactivate your virtual environment, simply run:

```bash
deactivate                # deactivates virtualenv
source .venv/bin/activate # reactivates virtualenv
```

## Validating the External Dependencies

## Debugging Issues

This repo makes use of various external tools.

### Debugging Issues with OpenAI

For additional details for validating issues:

* [OpenAI's Observability](https://platform.openai.com/logs)

Moreover, for validating the agent, the user can use the text defined in [prompt_for_chatgpt_v3.txt](src/piano_learning/resources/prompt_for_chatgpt_v3.txt) with an example user-provided MusicXML file.
