# AdMatch AI — Message Match Auditor

A Streamlit starter app for the DevSprint PS-03 problem statement.

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Create/activate a virtual environment if desired.
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Start the app:

   ```bash
   streamlit run app.py
   ```

## Use the app

- Choose **Try demo samples** to see the interface.
- For real judging, choose **Upload your CSV** and upload the organizer-provided ad dataset.
- Upload the matching offline `.html`, `.htm`, or `.txt` snapshot, or paste the supplied page content.
- Click **Analyze message match**.
- Export findings to CSV.

## CSV format

Required: `headline`, `description`

Recommended: `campaign_id`, `campaign_name`, `category`, `landing_page_url`, `snapshot_file`, `snapshot_text`.

If `snapshot_file` is set, the app looks for that file in the `snapshots/` directory. For uploaded snapshots, use the upload control.

## Important limitations

This is a working starter prototype using transparent lexical-overlap heuristics, not a production-grade semantic LLM auditor. Its score is a heuristic, not a conversion probability. Review findings against the actual data and seeded cases. Absence claims are not quoted as if they were page text. The app only labels an evidence quote verified when that exact normalized quote appears in the extracted source text.

For a stronger version, add an LLM that receives only the supplied ad copy and extracted snapshot text, returns schema-validated JSON, and then run the same exact-quote verification before displaying any finding. Never let the model invent page content.
