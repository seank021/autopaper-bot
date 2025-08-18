# Autopaper Bot
This project is designed to automate the process of summarizing research papers and matching the most relevant users based on their interests, in the Slack workspace.

## Features
- Summarizes research papers using OpenAI's GPT-4o model.
- Matches users with similar interests based on their paper summaries.
- QnA functionality to answer questions about the papers by tagging the bot in Slack.

## Database
- User data is stored in database.py. The Slack user ID is open since it is open publicly to other people in the Slack workspace.
- Paper metadata is stored in Supabase.
- This project is deployed on Render with a free plan.

## Flow
1. User uploads a research paper link in the Slack channel. (only arXiv papers are supported for now)
2. The bot detects the link, downloads the PDF file, and stores paper metadata in Supabase.
    - This downloading pdf itself is needed, in order to support the QnA functionality later.
3. The PDF text is extracted with `extract_text_from_pdf()` in `utils/pdf_utils.py`, and text is summarized using `summarize_text()` in `utils/summarizer.py`.
4. The summary is matched to lab members with `match_top_n_members()` in `utils/interest_matcher.py`, and the bot posts the summary + user mention in the reply of the corresponding thread.
5. If a user mentions the bot (@AutoPaper) in that thread with a question, the bot reloads the PDF (from cache or source link), extracts text again, and answers the question using `answer_question()` in `utils/qna.py`.

## Repository Structure
- `app.py`: Main application file that runs the bot and handles Slack events.
- `database/`
    - `member.py`: Contains the lab member data including their Slack user IDs, keywords, interests, and current works.
    - `project.py`: (TODO) Contains the project data including project channel Slack IDs, keywords, and descriptions.
- `scripts/embed_users.py`: Script to embed user interests for matching.
    - You should run this script after updating `database.py` if you plan to use user embeddings for matching interests.
- `user_embeddings/`: Contains the embeddings of each user generated from the `embed_users.py` script.
- `utils/`
    - `embedding_utils.py`: Contains functions to embed user database.
    - `interest_matcher.py`: Contains functions to match users based on their interests.
        - LLM matcher vs. Embedding matcher: The LLM matcher uses OpenAI's GPT-4o model to match users based on their interests, while the embedding matcher uses pre-computed embeddings of user interests for faster matching. Currently, the embedding matcher is being used.
    - `supabase_db.py`: Contains functions to insert and get paper metadata from Supabase.
    - `path_utils.py`: Contains functions to handle temp paths and file management.
    - `pdf_utils.py`: Contains functions to extract text from PDF files.
    - `link_utils.py`: Contains functions to support paper links for pdf extraction and metadata storage. (currently only supports arXiv links)
    - `summarizer.py`: Contains functions to summarize text using OpenAI's API.
    - `qna.py`: Contains functions to answer questions about the papers using OpenAI's API.
- `requirements.txt`: Contains the dependencies required to run the bot.
- `test/`: Contains test files for the bot.
    - Especially, you can run `test/paper_user_match.py` to test the user matching functionality, then compare the results `test/paper_user_match_results.json` with the expected results in `test/paper_user_match_answers.json`.
