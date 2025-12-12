# Slack Application Prompt

## Overview
This is going to be a Slack application app that is going to monitor user behavior and interactions in all public channels.

We are going to look at open channels and summarize a per user perspective, that when an admin wishes to respond to a member, he can get a deep understading of what he did, how involved is he. 

We will integrate with an llm model to generate answers and responses. that take into account company messaging, 
different web platforms to be scanned into a vector storage.

## Configuration
Sensitive credentials are stored in `.env` file:
- **SLACK_APP_ID**: Retrieved from environment variables
- **SLACK_TOKEN**: Retrieved from environment variables

> **Note**: Create a `.env` file in the project root with your Slack app credentials. This file should not be committed to version control. 