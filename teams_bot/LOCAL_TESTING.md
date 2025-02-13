# Local Testing Guide for Teams Bot

## Prerequisites

- Bot Framework Emulator
- Azure Functions Core Tools
- 1Password CLI (op)
- Node.js and npm
- Python 3.10+
- Conda

## Quick Start

```bash
# Install environment and tools
./tools/setup_local_env.sh

# Start the bot locally
./start-local.sh

# Launch Bot Framework Emulator
# Connect to: http://localhost:3978/api/messages
```

## Environment Setup

### 1. Install Bot Framework Emulator

**macOS**:
```bash
brew install --cask bot-framework-emulator
```

**Windows**:
- Download from [Bot Framework Emulator Releases](https://github.com/Microsoft/BotFramework-Emulator/releases)
- Run installer

**Linux**:
- Download AppImage from releases
- Make executable: `chmod +x BotFramework-Emulator-*-x86_64.AppImage`
- Run AppImage

### 2. Configure Local Environment

1. Copy `.env.template` to `.env`:
```bash
cp .env.template .env
```

2. Update environment variables:
```env
# Required for local testing
TEAMS_BOT_ID=
TEAMS_BOT_PASSWORD=
DEBUG=true
LOG_LEVEL=DEBUG
```

3. Configure local.settings.json:
```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_HTTPWORKER_PORT": "3978"
  },
  "Host": {
    "LocalHttpPort": 3978,
    "CORS": "*"
  }
}
```

## Test Scenarios

### 1. Basic Message Handling

1. Start bot locally
2. Open Bot Framework Emulator
3. Connect to `http://localhost:3978/api/messages`
4. Send test messages:
   - Basic text: "Hello"
   - Commands: "/help"
   - Special characters: "Test @#$%"

Expected:
- Bot responds appropriately
- No error messages in logs
- Response time < 2 seconds

### 2. Error Handling

Test various error scenarios:
1. Invalid commands
2. Malformed messages
3. Service unavailable scenarios

Expected:
- Graceful error messages
- Proper error logging
- No bot crashes

### 3. Conversation State

1. Start multi-turn conversation
2. Test context retention
3. Verify state cleanup

Expected:
- Context maintained between messages
- State properly updated
- Memory usage stable

### 4. Adaptive Cards

1. Test card rendering
2. Verify button actions
3. Check card updates

Expected:
- Cards render correctly
- Actions work as expected
- Updates are smooth

### 5. Authentication Flow (if applicable)

1. Test sign-in process
2. Verify token handling
3. Check token refresh

Expected:
- Smooth auth flow
- Proper token storage
- Secure handling

## Validation Steps

### 1. Environment Validation

```bash
# Run environment validator
python tools/validate_local_env.py

# Verify all tools installed
python tools/check_dependencies.py
```

### 2. Bot Health Check

```bash
# Run health checks
curl http://localhost:3978/api/health

# Check logs
tail -f logs/bot.log
```

### 3. Performance Testing

```bash
# Run basic load test
python tools/load_test.py --messages 100 --concurrent 10
```

## Troubleshooting

### Common Issues

1. **Port Already in Use**
```bash
# Check port usage
lsof -i :3978
# Kill process if needed
kill -9 <PID>
```

2. **Environment Issues**
```bash
# Recreate conda environment
conda env remove -n chatbot-llm
conda env create -f environment.yml
```

3. **Emulator Connection Failed**
- Verify bot is running
- Check firewall settings
- Ensure correct endpoint URL

### Logs

- Bot logs: `logs/bot.log`
- Azure Functions logs: `logs/func.log`
- Emulator logs: Available in Bot Framework Emulator

## Development Tips

1. **Hot Reload**
- Enable in `local.settings.json`:
```json
{
  "Values": {
    "AZURE_FUNCTIONS_ENVIRONMENT": "Development"
  }
}
```

2. **Debug Mode**
- Set `DEBUG=true` in `.env`
- Use VS Code debugger configuration

3. **Testing Tools**
- Use Postman collection in `tools/postman`
- Use `tools/test_messages.py` for automated testing

## Security Notes

1. Never commit `.env` files
2. Use 1Password for secrets
3. Rotate test credentials regularly
4. Monitor local network access

## Maintenance

1. Regular cleanup:
```bash
# Clean temporary files
./tools/cleanup.sh
```

2. Update dependencies:
```bash
# Update all dependencies
./tools/update_deps.sh
```

3. Verify environment:
```bash
# Full environment check
./tools/verify_env.sh
```
