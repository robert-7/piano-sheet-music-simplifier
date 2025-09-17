# Piano-Learning

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

```shell
sudo apt update
apt search openjdk | grep -E "openjdk-[0-9]+-jdk"
sudo apt install openjdk-17-jdk -y
java -version
```

```shell
# https://github.com/Audiveris/audiveris/releases/tag/5.7.1
_version="5.7.1"
_file="Audiveris-${_version}-ubuntu24.04-x86_64.deb"
_download_dir="/tmp"
wget -O "${_download_dir}/${_file}" "https://github.com/Audiveris/audiveris/releases/download/${_version}/${_file}"
sudo apt install "${_download_dir}/${_file}"
sudo ln -s /opt/audiveris/bin/Audiveris /usr/local/bin/audiveris
```

```shell
sudo apt install -y lilypond
which lilypond
lilypond --version

sudo snap install musescore
snap list musescore
```

### Recurring

To deactivate or reactivate your virtual environment, simply run:

```bash
deactivate                # deactivates virtualenv
source .venv/bin/activate # reactivates virtualenv
```

### Debugging

For additional details for

* [Linkup](https://app.linkup.so/home)
* [OpenAI Observability](https://platform.openai.com/logs)
