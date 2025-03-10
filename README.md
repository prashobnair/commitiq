# CommitIQ

CommitIQ is a SaaS platform designed to revolutionize technical recruiting by providing a more objective and insightful assessment of developers' skills and contributions based on their public GitHub activity.

## Overview

Traditional technical recruiting relies heavily on resumes, self-reported skills, and often superficial metrics like GitHub commit counts ("green squares"). These methods are easily gamed and don't accurately reflect a developer's true capabilities, coding style, collaboration skills, or the impact of their work.

CommitIQ analyzes a developer's public GitHub profile data (repositories, commits, pull requests, issues, reviews, etc.) to generate a comprehensive "Impact Score" and detailed insights. This score goes beyond simple activity counts and considers factors like:

- Code Quality
- Project Impact
- Collaboration
- Consistency
- Code Evolution

## Project Components

### GitHub User Database

The GitHub User Database tool efficiently collects and stores basic GitHub user data while respecting GitHub API rate limits. It supports parallel processing and resumable operations.

[Learn more about the GitHub User Database](github_user_db/README.md)

## Getting Started

### Prerequisites

- Python 3.7+
- Required packages (see component-specific requirements.txt files)
- GitHub API token (for higher rate limits)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/commitiq.git
   cd commitiq
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies for the specific component you want to use.

## License

[MIT License](LICENSE)
