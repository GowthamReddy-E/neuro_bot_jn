# Jenkins Status Bot for Webex Teams

A Webex Teams bot that provides real-time Jenkins build status information for multiple projects and teams.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Bot Credentials](#bot-credentials)
  - [Jenkins Credentials](#jenkins-credentials)
  - [Job Configuration](#job-configuration)
  - [Group Configuration](#group-configuration)
  - [Multiple Jenkins Instances](#multiple-jenkins-instances)
- [Usage](#usage)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## Features

- ✅ Monitor Jenkins builds across multiple instances
- ✅ Support for job groups (USM, IMS, etc.)
- ✅ Flexible alias system for easy job reference
- ✅ Multiple credential support for different Jenkins servers
- ✅ Real-time status updates with color-coded emojis
- ✅ IST timezone conversion
- ✅ Direct text responses (no unwanted cards)

## Project Structure

Current structure is organized to support future integrations (for example, Splunk) with reusable modules:

```text
neuro_bot/
├── bot_main.py
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── settings.py
│   │   ├── paths.py
│   │   ├── messages.py
│   │   └── command_utils.py
│   ├── clients/
│   │   ├── jenkins_api.py
│   │   └── splunk_api.py
│   ├── handlers/
│   │   └── status_command.py
│   ├── services/
│   │   ├── jenkins/
│   │   │   ├── config/
│   │   │       ├── job_config.ini
│   │   │       └── groups.ini
│   │   │   ├── catalog_service.py
│   │   │   └── credentials_service.py
│   │   └── splunk/
│   │       └── service.py
│   ├── cards/
│   │   └── job_card.py
│   └── integrations/
│       └── splunk/
│           └── client.py
└── start.sh
```

Design notes:
- `app/` is the single home for all Python application code.
- `app/core/` keeps shared settings, constants, and utility helpers.
- `app/clients/` handles external API calls.
- `app/services/` contains domain business logic.
- `app/handlers/` stays thin and focuses on command orchestration.
- `app/services/jenkins/config/` stores Jenkins job/group INI config files.

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd neuro_bot
   ```

2. **Set up Python environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure the bot** (see Configuration section below)

4. **Run the bot:**
   ```bash
   python bot_main.py
   ```

### Secure Secrets Workflow

Use one host-only secrets file so credentials are never committed and never generated inside the repo.

1. Create secrets file:
   ```bash
   mkdir -p ~/.config/neuro-bot
   cp .env.local.example ~/.config/neuro-bot/secrets.env
   chmod 600 ~/.config/neuro-bot/secrets.env
   ```

2. Fill real secret values in `~/.config/neuro-bot/secrets.env`.

3. Start container with one command:
   ```bash
   ./start.sh
   ```

`start.sh` automatically:
- requires and loads secrets from `~/.config/neuro-bot/secrets.env`
- builds and starts the `neuro-bot` container
- injects secrets into container via `--env-file`
- uses `job_config.ini` and `groups.ini` from inside the image by default
- sets container restart policy to `unless-stopped`

Equivalent Docker run command:
```bash
docker run -d --name neuro-bot \
   --restart unless-stopped \
   --user "$(id -u):$(id -g)" \
   --env-file "$HOME/.config/neuro-bot/secrets.env" \
   neuro-bot
```

Runtime config mount options:
By default, `job_config.ini` and `groups.ini` are used from inside the image.

Examples:
```bash
# Build image and run (default behavior)
./start.sh
```

### 24/7 Auto Start with systemd (`jbot` service)

Install and start the systemd service:

```bash
sudo ./scripts/systemd/install-systemd-service.sh
```

This installs and enables `jbot.service` so it starts on boot and keeps the bot container running continuously.

Common service commands:

```bash
systemctl status jbot.service
journalctl -u jbot.service -f
sudo systemctl restart jbot.service
sudo systemctl stop jbot.service
sudo systemctl disable jbot.service
```

Optional custom service name:

```bash
sudo ./scripts/systemd/install-systemd-service.sh <custom-name>
```

Environment precedence:
1. `~/.config/neuro-bot/secrets.env` (required)

Required variables in `~/.config/neuro-bot/secrets.env`:
- `WEBEX_BOT_TOKEN`
- `WEBEX_BOT_PERSON_ID`
- Per Jenkins instance from `app/services/jenkins/config/job_config.ini`, for example:
   - `JENKINS_FTD_ASA_USERNAME` / `JENKINS_FTD_ASA_TOKEN`
   - `JENKINS_SSP_USERNAME` / `JENKINS_SSP_TOKEN`
   - `JENKINS_BUILD_USERNAME` / `JENKINS_BUILD_TOKEN`
   - `JENKINS_SERVICE_USERNAME` / `JENKINS_SERVICE_TOKEN`

Optional launch override:
- `SECRETS_ENV_FILE=/custom/path/secrets.env ./start.sh`

## Configuration

### Bot Credentials

Recommended: keep credentials in `~/.config/neuro-bot/secrets.env` and inject them via `start.sh`.

Manual fallback (local only): create `config.py` only if you run the bot directly without env vars:

```python
# Get these from https://developer.webex.com/my-apps
WEBEX_BOT_TOKEN = "your_bot_token_here"
WEBEX_BOT_PERSON_ID = "your_bot_person_id_here"
```

### Jenkins Credentials

Recommended: keep Jenkins secrets in `~/.config/neuro-bot/secrets.env` using `JENKINS_<INSTANCE>_USERNAME` / `JENKINS_<INSTANCE>_TOKEN`.

Manual fallback (local only): configure Jenkins authentication in `app/services/jenkins/config/credentials.ini` only for non-container local runs:

#### Single Jenkins Instance:
```ini
[default]
username = your_jenkins_username
token = your_jenkins_api_token
```

#### Multiple Jenkins Instances:
```ini
[default]
username = user1
token = token1

[jenkins2]
username = user2
token = token2

[jenkins3]
username = user3
token = token3
```

**How to get Jenkins API Token:**
1. Log into Jenkins
2. Click your username → Configure
3. API Token → Add new Token
4. Copy the generated token

Security note:
- `~/.config/neuro-bot/secrets.env` is a local secret file and must not be committed.
- If a token is ever committed, revoke/rotate it immediately.

### Job Configuration

Configure jobs in `app/services/jenkins/config/job_config.ini`:

#### Basic Job Configuration:
```ini
[JOB_NAME]
url = https://your-jenkins.com/job/JobName/
alias = alias1, alias2, alias3
instance = default  # Optional: specify which credentials to use

[ANOTHER_JOB]
url = https://different-jenkins.com/job/AnotherJob/
alias = aj, anotherjob
instance = jenkins2  # Use different credentials

# URL mapping section (required)
[URLS]
JOB_NAME = https://your-jenkins.com/job/JobName/
ANOTHER_JOB = https://different-jenkins.com/job/AnotherJob/
```

#### Real-world Example:
```ini
[USM_7_88_MAIN]
url = https://engci-private-rtp.cisco.com/jenkins/ftd-asa/job/USM/job/IMS_7_88_MAIN/
alias = usm7.8, usm788, usm_main
instance = cisco_rtp

[IMS_10_0_MAIN]
url = https://engci-private-rtp.cisco.com/jenkins/ftd-asa/job/IMS/job/IMS_BUILD/job/IMS_10_0_MAIN/
alias = i10, ims10, main10
instance = cisco_rtp

[EXTERNAL_PROJECT]
url = https://external-jenkins.company.com/job/ExternalProject/
alias = ext, external
instance = external_creds

[URLS]
USM_7_88_MAIN = https://engci-private-rtp.cisco.com/jenkins/ftd-asa/job/USM/job/IMS_7_88_MAIN/
IMS_10_0_MAIN = https://engci-private-rtp.cisco.com/jenkins/ftd-asa/job/IMS/job/IMS_BUILD/job/IMS_10_0_MAIN/
EXTERNAL_PROJECT = https://external-jenkins.company.com/job/ExternalProject/
```

#### Corresponding Credentials:
```ini
[default]
username = cisco_user
token = cisco_token_123

[cisco_rtp]
username = cisco_user
token = cisco_token_123

[external_creds]
username = external_user
token = external_token_456
```

### Group Configuration

Organize jobs into logical groups in `app/services/jenkins/config/groups.ini`:

```ini
[USM]
jobs = USM_7_6_MAIN, USM_7_7_MAIN, USM_7_8_MAIN, USM_7_88_MAIN

[IMS]
jobs = IMS_10_0_MAIN, IMS_7_6_MAIN, IMS_7_7_MAIN, IMS_7_4_1_MAIN, BAZEL_IMS_10_0

[EXTERNAL]
jobs = EXTERNAL_PROJECT, ANOTHER_EXTERNAL_JOB

[ALL_CRITICAL]
jobs = USM_7_88_MAIN, IMS_10_0_MAIN, EXTERNAL_PROJECT
```

### Multiple Jenkins Instances

To support multiple Jenkins instances with different credentials:

1. **Set credentials in `~/.config/neuro-bot/secrets.env`:**
   ```bash
   JENKINS_DEFAULT_USERNAME=primary_user
   JENKINS_DEFAULT_TOKEN=primary_token

   JENKINS_SECONDARY_USERNAME=secondary_user
   JENKINS_SECONDARY_TOKEN=secondary_token

   JENKINS_PROD_USERNAME=prod_user
   JENKINS_PROD_TOKEN=prod_token
   ```

2. **Update job_config.ini with instance mapping:**
   ```ini
   [JOB_ON_PRIMARY]
   url = https://primary-jenkins.com/job/MyJob/
   alias = primary, main
   instance = default

   [JOB_ON_SECONDARY]
   url = https://secondary-jenkins.com/job/MyJob/
   alias = secondary, backup
   instance = secondary

   [JOB_ON_PROD]
   url = https://prod-jenkins.com/job/MyJob/
   alias = prod, production
   instance = prod
   ```

3. **The bot will automatically use the correct credentials** from environment variables based on the `instance` field.

## Usage

### Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `@bot jenkins` | Show all jobs | `@bot jenkins` |
| `@bot usm` | Show USM group jobs | `@bot usm` |
| `@bot ims` | Show IMS group jobs | `@bot ims` |
| `@bot status` | Show all jobs | `@bot status` |
| `@bot [alias]` | Show specific job | `@bot usm7.8` |

### Supported Aliases

You can use any alias defined in the job configuration:
- `@bot usm7.8` → USM_7_88_MAIN
- `@bot i10` → IMS_10_0_MAIN  
- `@bot main10` → IMS_10_0_MAIN

## Examples

### Example 1: Basic Setup (Single Jenkins)
```ini
# ~/.config/neuro-bot/secrets.env
WEBEX_BOT_TOKEN=your_bot_token
WEBEX_BOT_PERSON_ID=your_bot_person_id
JENKINS_DEFAULT_USERNAME=john.doe
JENKINS_DEFAULT_TOKEN=abc123def456

# job_config.ini
[MY_PROJECT]
url = https://jenkins.mycompany.com/job/MyProject/
alias = mp, myproj, project

[URLS]
MY_PROJECT = https://jenkins.mycompany.com/job/MyProject/

# groups.ini
[MAIN]
jobs = MY_PROJECT
```

### Example 2: Multiple Teams Setup
```ini
# ~/.config/neuro-bot/secrets.env
WEBEX_BOT_TOKEN=your_bot_token
WEBEX_BOT_PERSON_ID=your_bot_person_id
JENKINS_DEFAULT_USERNAME=shared_user
JENKINS_DEFAULT_TOKEN=shared_token
JENKINS_TEAM_A_USERNAME=team_a_user
JENKINS_TEAM_A_TOKEN=team_a_token
JENKINS_TEAM_B_USERNAME=team_b_user
JENKINS_TEAM_B_TOKEN=team_b_token

# job_config.ini
[TEAM_A_FRONTEND]
url = https://jenkins-a.company.com/job/Frontend/
alias = frontend, fe, ui
instance = team_a

[TEAM_A_BACKEND]
url = https://jenkins-a.company.com/job/Backend/
alias = backend, be, api
instance = team_a

[TEAM_B_SERVICE]
url = https://jenkins-b.company.com/job/Service/
alias = service, svc
instance = team_b

[URLS]
TEAM_A_FRONTEND = https://jenkins-a.company.com/job/Frontend/
TEAM_A_BACKEND = https://jenkins-a.company.com/job/Backend/
TEAM_B_SERVICE = https://jenkins-b.company.com/job/Service/

# groups.ini
[TEAM_A]
jobs = TEAM_A_FRONTEND, TEAM_A_BACKEND

[TEAM_B]
jobs = TEAM_B_SERVICE

[ALL_TEAMS]
jobs = TEAM_A_FRONTEND, TEAM_A_BACKEND, TEAM_B_SERVICE
```

### Example Bot Responses

**Success Response:**
```
🟢 [USM_7_88_MAIN #1234](https://jenkins.com/job/USM/1234/)
TRD: 2025-09-21 TRT: 02:30 PM Duration: 00:45:23 Status: SUCCESS
```

**Error Response:**
```
❌ **USM_7_88_MAIN** - HTTP 401: Unauthorized
```

**No Match Response:**
```
❌ No job found for `random`.

**Available commands:**
• `@bot jenkins` - Show all jobs
• `@bot usm` - Show USM jobs
• `@bot ims` - Show IMS jobs
• `@bot status` - Show all jobs

**Individual jobs (use aliases):**
• `usm7.8`, `usm7.88_mian`, `usm_7.8_main`
• `i10`, `main10` (for IMS 10.0)

Please use the correct keywords.
```

## Troubleshooting

### Common Issues

1. **"No job found" error:**
   - Check if job name exists in `job_config.ini`
   - Verify the job name matches exactly in the `[URLS]` section
   - Check if aliases are spelled correctly

2. **"HTTP 401: Unauthorized" error:**
   - Verify Jenkins username and token in `~/.config/neuro-bot/secrets.env`
   - Check if the token has necessary permissions
   - Ensure the `instance` field matches env vars like `JENKINS_<INSTANCE>_USERNAME/TOKEN`

3. **"HTTP 404: Not Found" error:**
   - Verify the Jenkins URL is correct
   - Check if the job exists and is accessible
   - Ensure the URL format includes the trailing slash

4. **"Missing build information" error:**
   - Job might not have been built yet
   - Check Jenkins job manually to verify it has build history

5. **Bot not responding:**
   - Check bot token and person ID in `~/.config/neuro-bot/secrets.env`
   - Verify the bot is running without errors
   - Check Webex Teams bot permissions

### Debug Mode

To enable debug logging, run:
```bash
export WEBEX_BOT_DEBUG=1
python bot_main.py
```

### Log Files

Check logs for detailed error information:
- Bot startup errors: Check console output
- Jenkins API errors: Look for HTTP status codes in responses
- Configuration errors: Verify all required sections exist

### Testing Configuration

Test individual components:
```python
# Test credentials
from jenkins.jenkins_fetcher import read_credentials
username, token = read_credentials(None, "default")
print(f"Default credentials: {username}")

# Test job config
import configparser
config = configparser.ConfigParser()
config.read("app/services/jenkins/config/job_config.ini")
print("Jobs:", config.sections())
```

## Security Considerations

1. **Never commit credentials to version control**
2. **Use Jenkins API tokens instead of passwords**
3. **Limit bot access to specific Webex rooms if possible**
4. **Regularly rotate Jenkins API tokens**
5. **Use environment variables for sensitive data in production**

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review configuration file syntax
3. Test Jenkins URLs manually in a browser
4. Check Jenkins server logs for authentication issues

---

**Note:** This bot requires network access to Jenkins instances and Webex Teams. Ensure firewall rules allow necessary connections.
