#!/usr/bin/env python3
"""
Content Bot - Turns GitHub commits into social media draft posts
"""

import os
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional

import typer
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = typer.Typer(help="Generate social media content from GitHub commits")

class ContentBot:
    def __init__(self):
        self.github_token = os.getenv("TOKEN")
        self.openrouter_api_key = os.getenv("API")  # Using same env var for compatibility
        self.state_file = Path("state.json")
        self.output_dir = Path("out")
        
        if not self.github_token:
            typer.echo("❌ TOKEN not found in environment variables", err=True)
            raise typer.Exit(1)
        
        # Ensure output directory exists
        self.output_dir.mkdir(exist_ok=True)
    
    def load_state(self) -> Dict:
        """Load state from state.json file"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"last_run_at": None}
    
    def save_state(self) -> None:
        """Save current state to state.json file"""
        state = {
            "last_run_at": datetime.now(timezone.utc).isoformat()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def fetch_commits(self, repo: str, days: int) -> List[Dict]:
        """Fetch commits from GitHub API"""
        url = f"https://api.github.com/repos/{repo}/commits"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Calculate date range
        since_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        params = {
            "since": since_date,
            "per_page": 100
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            typer.echo(f"❌ Error fetching commits: {e}", err=True)
            raise typer.Exit(1)
    
    def filter_commits_by_content(self, commits: List[Dict]) -> List[Dict]:
        """Filter out commits that are chores or tests"""
        filtered_commits = []
        
        for commit in commits:
            commit_msg = commit['commit']['message'].lower()
            
            # Skip commits that start with 'chore:' or contain 'tests/'
            if commit_msg.startswith('chore:') or 'tests/' in commit_msg:
                continue
                
            filtered_commits.append(commit)
        
        return filtered_commits
    
    def filter_commits_by_state(self, commits: List[Dict]) -> List[Dict]:
        state = self.load_state()
        last_run_at = state.get("last_run_at")
        
        if not last_run_at:
            # First run - return all commits
            return commits
        
        # Parse last run timestamp - handle both with and without timezone
        try:
            if last_run_at.endswith('Z'):
                last_run_time = datetime.fromisoformat(last_run_at.replace('Z', '+00:00'))
            elif '+' in last_run_at or last_run_at.count('-') > 2:
                last_run_time = datetime.fromisoformat(last_run_at)
            else:
                # No timezone info, assume local timezone and convert to UTC for comparison
                last_run_time = datetime.fromisoformat(last_run_at).replace(tzinfo=timezone.utc)
        except ValueError:
            # Fallback for any parsing issues
            last_run_time = datetime.fromisoformat(last_run_at).replace(tzinfo=timezone.utc)
        
        new_commits = []
        for commit in commits:
            commit_date_str = commit['commit']['author']['date']
            # Parse commit date - GitHub API always returns UTC timestamps
            if commit_date_str.endswith('Z'):
                commit_date = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))
            else:
                commit_date = datetime.fromisoformat(commit_date_str)
                if commit_date.tzinfo is None:
                    commit_date = commit_date.replace(tzinfo=timezone.utc)
            
            if commit_date > last_run_time:
                new_commits.append(commit)
        
        return new_commits
    
    def sanitize_content(self, text: str) -> str:
        secret_patterns = [
            r'[A-Za-z0-9]{20,}',
            r'sk-[A-Za-z0-9]{32,}',
            r'ghp_[A-Za-z0-9]{36}',
            r'ghs_[A-Za-z0-9]{36}',
            r'password\s*[:=]\s*[^\s]+',
            r'token\s*[:=]\s*[^\s]+',
        ]
        
        sanitized = text
        for pattern in secret_patterns:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        sanitized = re.sub(r'\b[A-Z][a-z]+Corp\b', 'Client', sanitized)
        sanitized = re.sub(r'\b[A-Z][a-z]+Inc\b', 'Customer', sanitized)
        
        return sanitized
    
    def generate_with_openrouter(self, commits_for_content: List[Dict], new_commits: List[Dict], all_commits: List[Dict]) -> Optional[Dict[str, str]]:
        """Generate content using OpenRouter API"""
        if not self.openrouter_api_key:
            return None
        
        try:
            import openai
            client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_api_key
            )
            
            # Prepare detailed commit information
            commit_details = []
            new_commit_details = []
            
            # Process new commits (priority)
            for commit in new_commits:
                commit_date = commit['commit']['author']['date'][:10]
                commit_msg = commit['commit']['message']
                
                lines = commit_msg.split('\n')
                title = lines[0].strip()
                body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ""
                
                commit_info = f"[{commit_date}] {title}"
                if body:
                    commit_info += f" - {body[:100]}..." if len(body) > 100 else f" - {body}"
                
                new_commit_details.append(commit_info)
            
            # Process older commits for context
            older_commits = [c for c in all_commits if c not in new_commits]
            for commit in older_commits[:3]:  # Only include 3 older commits for context
                commit_date = commit['commit']['author']['date'][:10]
                commit_msg = commit['commit']['message']
                
                lines = commit_msg.split('\n')
                title = lines[0].strip()
                
                commit_info = f"[{commit_date}] {title}"
                commit_details.append(commit_info)
            
            # Combine for prompt
            if new_commit_details:
                commits_text = "NEW COMMITS (focus on these):\n" + '\n'.join(new_commit_details)
                if commit_details:
                    commits_text += "\n\nOLDER COMMITS (brief context only):\n" + '\n'.join(commit_details)
            else:
                commits_text = '\n'.join([c for c in commit_details] + [c for c in new_commit_details])
            
            # Always prioritize new commits heavily (90% focus)
            prompt = f"""Based on these ACTUAL commit messages, create social media posts:

{commits_text}

REQUIREMENTS:
- Focus 90% on NEW COMMITS section (these are the main achievements)
- Only use older commits for brief context (10% of content)
- Use exact terminology from commit messages
- Do NOT invent features not mentioned in commits

Create two posts:

TWITTER: (180-260 chars) Focus almost entirely on NEW commits with emojis and hashtags

LINKEDIN: (400-700 chars) Professional post highlighting NEW work primarily, minimal older context

CRITICAL: NEW COMMITS are the main story - older commits are just background context."""
            
            response = client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.8
            )
            
            content = response.choices[0].message.content
            
            
            # Parse the response - robust parsing for different AI model formats
            twitter_version = ""
            linkedin_version = ""
            
            # Clean up the content and split into sections
            content = content.strip()
            
            # Method 1: Look for explicit TWITTER: and LINKEDIN: markers
            import re
            
            # Try to find TWITTER: section
            twitter_match = re.search(r'TWITTER:\s*(.*?)(?=LINKEDIN:|$)', content, re.DOTALL | re.IGNORECASE)
            if twitter_match:
                twitter_version = twitter_match.group(1).strip()
            
            # Try to find LINKEDIN: section  
            linkedin_match = re.search(r'LINKEDIN:\s*(.*?)(?=TWITTER:|$)', content, re.DOTALL | re.IGNORECASE)
            if linkedin_match:
                linkedin_version = linkedin_match.group(1).strip()
            
            # Method 2: If no explicit markers, try to parse by structure
            if not twitter_version or not linkedin_version:
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                
                # Look for content that looks like social media posts
                potential_posts = []
                current_post = ""
                
                for line in lines:
                    # Skip headers and labels
                    if any(keyword in line.upper() for keyword in ['VERSION', 'CHARS', 'TWITTER', 'LINKEDIN']) and len(line) < 50:
                        if current_post:
                            potential_posts.append(current_post.strip())
                            current_post = ""
                        continue
                    
                    # Skip hashtag-only lines
                    if line.startswith('#') and len(line.split()) <= 5:
                        continue
                    
                    # Accumulate post content
                    if current_post:
                        current_post += " " + line
                    else:
                        current_post = line
                
                # Add the last post if exists
                if current_post:
                    potential_posts.append(current_post.strip())
                
                # Assign posts based on length (Twitter is usually shorter)
                if len(potential_posts) >= 2:
                    # Sort by length to identify Twitter (shorter) vs LinkedIn (longer)
                    potential_posts.sort(key=len)
                    if not twitter_version:
                        twitter_version = potential_posts[0]
                    if not linkedin_version:
                        linkedin_version = potential_posts[-1] if len(potential_posts) > 1 else potential_posts[0]
                elif len(potential_posts) == 1:
                    # If only one post found, use it for both (better than nothing)
                    post = potential_posts[0]
                    if not twitter_version:
                        twitter_version = post[:260]  # Truncate for Twitter
                    if not linkedin_version:
                        linkedin_version = post
            
            # Clean up the extracted content
            twitter_version = re.sub(r'\s+', ' ', twitter_version).strip()
            linkedin_version = re.sub(r'\s+', ' ', linkedin_version).strip()
            
            # Remove any remaining labels
            twitter_version = re.sub(r'^(TWITTER:?|Twitter:?)\s*', '', twitter_version, flags=re.IGNORECASE)
            linkedin_version = re.sub(r'^(LINKEDIN:?|LinkedIn:?)\s*', '', linkedin_version, flags=re.IGNORECASE)
            
            return {
                "twitter": twitter_version[:260],  # Ensure within limits
                "linkedin": linkedin_version[:700]
            }
            
        except Exception as e:
            typer.echo(f"⚠️ OpenRouter generation failed: {e}")
            return None
    
    def generate_template_fallback(self, commits: List[Dict]) -> Dict[str, str]:
        commit_count = len(commits)
        
        if commit_count == 0:
            return {
                "twitter": "No recent updates to share 🤔 #coding #development",
                "linkedin": "Taking a moment to plan the next phase of development. Sometimes the best progress happens in the thinking phase! 🧠 #development #planning #coding"
            }
        
        commit_messages = []
        for commit in commits[:4]:
            msg = commit['commit']['message'].split('\n')[0]
            if len(msg) > 60:
                msg = msg[:57] + "..."
            commit_messages.append(msg)
        
        if commit_count == 1:
            twitter_version = f"✅ {commit_messages[0]} #coding #development"
        else:
            twitter_version = f"Productive week with {commit_count} updates! Latest: {commit_messages[0]} 🚀 #coding #development"
        
        linkedin_version = f"""Recent development progress ({commit_count} commits):

"""
        
        for i, msg in enumerate(commit_messages[:3]):
            linkedin_version += f"• {msg}\n"
        
        if commit_count > 3:
            linkedin_version += f"• ...and {commit_count - 3} more improvements\n"
        
        linkedin_version += f"""
Continuous improvement and feature development in progress! 💪 #development #coding #progress"""
        
        return {
            "twitter": twitter_version[:260],
            "linkedin": linkedin_version[:700]
        }
    
    def create_github_issue(self, repo: str, title: str, content: str):
        """Create a GitHub issue with the draft content"""
        url = f"https://api.github.com/repos/{repo}/issues"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        data = {
            "title": title,
            "body": content,
            "labels": ["content-draft", "social-media"]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            issue_data = response.json()
            typer.echo(f"✅ Created GitHub issue: {issue_data['html_url']}")
        except requests.exceptions.RequestException as e:
            typer.echo(f"⚠️ Failed to create GitHub issue: {e}")
    
    
    def save_draft(self, content: Dict[str, str], commits: List[Dict]) -> str:
        """Save draft to markdown file"""
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"draft_{today}.md"
        filepath = self.output_dir / filename
        
        markdown_content = f"""# Social Media Draft - {today}

## Twitter/X Version
{content['twitter']}

## LinkedIn Version
{content['linkedin']}

---

## Source Commits ({len(commits)} total)
"""
        
        for commit in commits[:10]:  # Show up to 10 commits
            commit_date = commit['commit']['author']['date'][:10]
            commit_msg = commit['commit']['message'].split('\n')[0]
            commit_url = commit['html_url']
            markdown_content += f"- [{commit_date}] {commit_msg} ([view]({commit_url}))\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return str(filepath)

@app.command()
def main(
    repo: str = typer.Option(..., "--repo", "-r", help="GitHub repository (owner/repo)"),
    days: int = typer.Option(3, "--days", "-d", help="Number of days to look back for commits"),
):
    """Generate social media content from recent GitHub commits"""
    
    typer.echo(f"🤖 Content Bot starting...")
    typer.echo(f"📊 Analyzing {repo} for commits in the last {days} days")
    
    bot = ContentBot()
    
    # Fetch commits
    all_commits = bot.fetch_commits(repo, days)
    typer.echo(f"📥 Found {len(all_commits)} total commits")
    
    # Filter by content
    filtered_commits = bot.filter_commits_by_content(all_commits)
    
    # Filter by state
    new_commits = bot.filter_commits_by_state(filtered_commits)
    typer.echo(f"🆕 Found {len(new_commits)} new commits since last run")
    
    if not new_commits:
        typer.echo("✨ No updates this run")
        bot.save_state()
        return
    
    # Use new commits for content generation
    commits_for_content = new_commits
    
    # Sanitize commit messages
    for commit in commits_for_content:
        commit['commit']['message'] = bot.sanitize_content(commit['commit']['message'])
    
    # Generate content
    typer.echo("🎨 Generating content...")
    content = bot.generate_with_openrouter(commits_for_content, new_commits, filtered_commits)
    
    if not content:
        typer.echo("📝 Using template fallback (OpenRouter not available)")
        content = bot.generate_template_fallback(commits_for_content)
    else:
        typer.echo("🤖 Generated content with OpenRouter")
    
    # Sanitize generated content
    content['twitter'] = bot.sanitize_content(content['twitter'])
    content['linkedin'] = bot.sanitize_content(content['linkedin'])
    
    # Save draft
    draft_path = bot.save_draft(content, commits_for_content)
    typer.echo(f"💾 Saved draft to: {draft_path}")
    
    # Create GitHub issue
    today = datetime.now().strftime("%Y-%m-%d")
    issue_title = f"Social Media Draft - {today}"
    issue_content = f"""## Twitter/X Version
{content['twitter']}

## LinkedIn Version
{content['linkedin']}

---
*Generated from {len(new_commits)} commits*"""
    
    bot.create_github_issue(repo, issue_title, issue_content)
    
    # Update state with current timestamp
    bot.save_state()
    typer.echo("✅ Content bot completed successfully!")

if __name__ == "__main__":
    app()
