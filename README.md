# Content Bot 🤖

A CLI tool that turns recent GitHub commits into social media draft posts for LinkedIn and Twitter/X.

## Features

- ✅ Fetches commits from GitHub API for the last N days
- ✅ Generates Twitter/X (180-260 chars) and LinkedIn (400-700 chars) versions
- ✅ Uses OpenAI for smart content generation (with template fallback)
- ✅ **NEW: AI-powered image generation** with DALL-E or custom graphics
- ✅ Filters out secrets and sensitive information
- ✅ Saves drafts to markdown files in `/out/` directory
- ✅ Creates GitHub Issues with the draft content
- ✅ Maintains state to avoid processing duplicate commits

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your tokens
   ```

3. **Get required tokens:**
   - **GitHub Token**: Go to [GitHub Settings > Tokens](https://github.com/settings/tokens) and create a personal access token with `repo` scope
   - **OpenRouter API Key**: Get from [OpenRouter Platform](https://openrouter.ai/keys) for AI-powered content generation

## GitHub Actions / Secrets Setup

If deploying via GitHub Actions, store your environment variables as GitHub Secrets:

1. Go to your repository **Settings > Secrets and variables > Actions**
2. Add the following secrets:
   - `GITHUB_TOKEN`: Your GitHub personal access token
   - `OPENAI_API_KEY`: Your OpenRouter API key

The `.env` file is excluded from git via `.gitignore` for security.

## Usage

```bash
# Basic usage - analyze last 3 days (includes image generation)
python content_bot.py --repo yourusername/yourrepo

# Custom time range
python content_bot.py --repo yourusername/yourrepo --days 7

# Skip image generation (text only)
python content_bot.py --repo yourusername/yourrepo --no-image

# Short form
python content_bot.py -r yourusername/yourrepo -d 5
```

## Example Output

The tool generates:

### Twitter/X Version (180-260 chars)
```
Shipped 5 updates this week! 🚀 Key improvements include better functionality and bug fixes. #coding #development #progress
```

### LinkedIn Version (400-700 chars)
```
Made 5 commits this week, focusing on continuous improvement and feature development.

Recent highlights:
• Fix authentication bug in user login
• Add new dashboard analytics feature
• Improve API response times by 40%

Always working to deliver better solutions! 💪 #development #coding #progress
```

## Files Created

- `out/draft_YYYY-MM-DD.md` - Markdown file with the draft content
- `out/images/social_post_YYYY-MM-DD.png` - Generated social media image
- `state.json` - Tracks last run time to avoid duplicates
- GitHub Issue with the same content

## 🎨 Image Generation

The bot now creates engaging visual content to accompany your posts:

### AI-Generated Images (DALL-E)
- **Requires**: OpenAI API key
- **Quality**: Professional, custom-designed images
- **Style**: Modern, tech-focused, social media optimized
- **Format**: 1024x1024 PNG (perfect for social platforms)

### Custom Graphics (Fallback)
- **No API required**: Works without OpenAI
- **Features**: Commit statistics, progress metrics, modern design
- **Style**: Dark theme with gradient backgrounds
- **Customizable**: Shows your actual commit messages and counts

### Image Features
- 📊 **Commit Statistics**: Visual representation of your progress
- 🎨 **Professional Design**: Clean, modern aesthetics
- 📱 **Social Media Ready**: Optimized dimensions for all platforms
- 🔧 **Automatic Generation**: No manual design work needed

## Safety Features

- **Secret Detection**: Automatically removes API keys, tokens, and passwords
- **Content Sanitization**: Replaces client/org names with generic terms
- **Fallback Mode**: Works without OpenAI API key using templates

## Troubleshooting

### "GITHUB_TOKEN not found"
Make sure you've created a `.env` file with your GitHub token:
```
GITHUB_TOKEN=your_token_here
```

### "No updates this run"
This means no new commits were found since the last run. The tool tracks processed commits in `state.json`.

### OpenAI API Issues
If OpenAI fails, the tool automatically falls back to template-based generation.

## License

MIT License - feel free to modify and use as needed!
