# Autopaper Bot
This project is designed to automate the process of summarizing research papers and matching the most relevant users based on their interests, in the Slack workspace.

## Features
- Summarizes research papers using OpenAI's GPT-4.1-nano model.
- Matches users with similar interests based on their paper summaries.
- QnA functionality to answer questions about the papers by tagging the bot in Slack.

## Database
- User data is stored in database.py. The Slack user ID is open since it is open publicly to other people in the Slack workspace.
- Paper metadata is stored in Supabase.
- This project is deployed on Google Cloud Run. So when you change the code and want to redeploy, run the following commands:
    ```
    gcloud builds submit --tag gcr.io/striking-goal-472721-a9/autopaper
    
    gcloud run deploy autopaper --image gcr.io/striking-goal-472721-a9/autopaper --platform managed --region asia-northeast3 --allow-unauthenticated --memory 1Gi --cpu 1 --min-instances 1 --max-instances 2
    ```

## Flow
1. User uploads a research paper link in the Slack channel. (only arXiv papers are supported for now)
2. The bot detects the link, downloads the PDF file, and stores paper metadata in Supabase.
    - This downloading pdf itself is needed, in order to support the QnA functionality later.
3. The PDF text is extracted with `extract_text_from_pdf()` in `utils/pdf_utils.py`, and text is summarized using `summarize_text()` in `utils/summarizer.py`.
4. The summary is matched to lab members with `match_top_n_members()` in `utils/interest_matcher.py`, and the bot posts the summary + user mention in the reply of the corresponding thread.
5. If a user mentions the bot (@AutoPaper) in that thread with a question, the bot reloads the PDF (from cache or source link), extracts text again, and answers the question using `answer_question()` in `utils/qna.py`.

## Repository Structure
- `app.py`: Main application file that runs the bot and handles Slack events.
- `utils/`
    - `embedding_utils.py`: Contains functions to embed user database.
    - `member_tagger.py`: Contains functions to match users based on their interests.
    - `supabase_db.py`: Contains functions to insert and get paper metadata from Supabase.
    - `path_utils.py`: Contains functions to handle temp paths and file management.
    - `pdf_utils.py`: Contains functions to extract text from PDF files.
    - `link_utils.py`: Contains functions to support paper links for pdf extraction and metadata storage. (currently only supports arXiv links)
    - `summarizer.py`: Contains functions to summarize text using OpenAI's API.
    - `qna.py`: Contains functions to answer questions about the papers using OpenAI's API.
    - `user_info.py`: Contains functions to get user information from Slack API.
- `requirements.txt`: Contains the dependencies required to run the bot.
- `database/` - Not using for deploy version, since we're using Supabase.
    - `member.py`: Contains the lab member data including their Slack user IDs, keywords, and interests.
    - `project.py`: (TODO) Contains the project data including project channel Slack IDs, keywords, and descriptions.
- `scripts/`
    - `add_member_on_supabase.py`: Script to add lab members to Supabase.
    - `embed_users.py`: Script to embed user interests for matching.
- `user_embeddings/`: Contains the embeddings of each user generated from the `embed_users.py` script.
- `test/`: Contains test files for the bot.