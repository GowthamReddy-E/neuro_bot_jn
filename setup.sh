#!/bin/bash

# Jenkins Status Bot Setup Script

echo "🤖 Jenkins Status Bot Setup"
echo "==========================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Copy example configuration files if they don't exist
echo "📝 Setting up configuration files..."

if [ ! -f "jenkins/credentials.ini" ]; then
    echo "  → Creating credentials.ini from example..."
    cp jenkins/credentials.ini.example jenkins/credentials.ini
    echo "  ⚠️  Please edit jenkins/credentials.ini with your Jenkins credentials"
fi

if [ ! -f "jenkins/job_config.ini" ]; then
    echo "  → Creating job_config.ini from example..."
    cp jenkins/job_config.ini.example jenkins/job_config.ini
    echo "  ⚠️  Please edit jenkins/job_config.ini with your Jenkins jobs"
fi

if [ ! -f "jenkins/groups.ini" ]; then
    echo "  → Creating groups.ini from example..."
    cp jenkins/groups.ini.example jenkins/groups.ini
    echo "  ⚠️  Please edit jenkins/groups.ini with your job groups"
fi

# Check if config.py exists
if [ ! -f "config.py" ]; then
    echo "  → Creating config.py template..."
    cat > config.py << 'EOF'
# Webex Bot Configuration
# Get these from https://developer.webex.com/my-apps

WEBEX_BOT_TOKEN = "your_bot_token_here"
WEBEX_BOT_PERSON_ID = "your_bot_person_id_here"
EOF
    echo "  ⚠️  Please edit config.py with your Webex bot credentials"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit config.py with your Webex bot credentials"
echo "2. Edit jenkins/credentials.ini with your Jenkins credentials"  
echo "3. Edit jenkins/job_config.ini with your Jenkins jobs"
echo "4. Edit jenkins/groups.ini with your job groups"
echo "5. Run the bot: python bot_main.py"
echo ""
echo "📖 For detailed configuration help, see README.md"
echo ""
echo "🚀 To start the bot now:"
echo "   python bot_main.py"