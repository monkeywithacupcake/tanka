import logging
from typing import Dict

from atproto import Client, models

logger = logging.getLogger(__name__)


class TankaPoster:

    def __init__(self, 
                 user_name: str = None, app_pword: str = None):

        self.client = Client()
        self.client.login(user_name, app_pword)
        logger.info(f"Logged in as {self.client.me.display_name}")

    def create_thread(self, *posts):
        """
        Creates a thread. The first argument is the root post, 
        and all following arguments are sequential replies.
        """
        if not posts:
            return

        # 1. Send the Root Post
        root_response = self.client.send_post(text=posts[0])
        # Create a 'strong reference' for the root
        root_ref = models.create_strong_ref(root_response)
        
        # Track the last post sent to use as the 'parent' for the next reply
        parent_ref = root_ref

        # 2. Iterate through remaining strings as replies
        for post_text in posts[1:]:
            reply_response = self.client.send_post(
                text=post_text,
                reply_to=models.AppBskyFeedPost.ReplyRef(
                    parent=parent_ref, 
                    root=root_ref
                )
            )
            # Update parent_ref to the post we just sent
            parent_ref = models.create_strong_ref(reply_response)

    def format_top_species_post(self, analysis: Dict) -> str:
        """Format top species for a Bluesky post (compact, no counts)"""
        if not analysis or 'top_species' not in analysis:
            return ""

        lines = ["Top Birds Detected:"]
        for i, (species, _) in enumerate(analysis['top_species'], 1):
            lines.append(f"{i}. {species}")

        return "\n".join(lines)

    def format_summary_post(self, analysis: Dict) -> str:
        """Format brief summary for a Bluesky post"""
        if not analysis:
            return ""

        # Extract date from filename (format: boxname_YYYY-MM-DD.csv)
        date_str = ""
        if 'file' in analysis:
            parts = analysis['file'].replace('.csv', '').split('_')
            if len(parts) >= 2:
                date_str = parts[-1]
        elif 'files' in analysis and analysis['files']:
            parts = analysis['files'][0].replace('.csv', '').split('_')
            if len(parts) >= 2:
                date_str = parts[-1]

        total = analysis.get('total_detections', 0)
        filtered = analysis.get('filtered_detections', 0)
        unique = analysis.get('unique_species', 0)
        threshold = analysis.get('score_threshold', 0.5)

        return (f"Summary: {date_str}\n"
                f"Total detections: {total}\n"
                f"With confidence (>{threshold}): {filtered}\n"
                f"Unique species: {unique}")

    def format_new_birds_post(self, analysis: Dict) -> str:
        """Format new/rare birds for a Bluesky post (empty if none)"""
        if not analysis:
            return ""

        new_birds = analysis.get('new_birds', [])
        if not new_birds:
            return ""

        lines = ["New arrivals (not seen in 7 days):"]
        for bird in new_birds:
            lines.append(f"• {bird}")

        return "\n".join(lines)

    def post_analysis(self, analysis: Dict) -> None:
        """
        Format and post analysis results as a thread

        Args:
            analysis: Analysis results dictionary (from JSON)
        """
        top_species_post = self.format_top_species_post(analysis)
        summary_post = self.format_summary_post(analysis)
        new_birds_post = self.format_new_birds_post(analysis)

        posts = [top_species_post, summary_post]
        if new_birds_post:
            posts.append(new_birds_post)

        logger.info(f"Creating thread with {len(posts)} posts")
        self.create_thread(*posts)


# --- Usage Example ---
# Replace with values from your config file
#my_bot = BlueskyThreader("handle.bsky.social", "your-app-password")

#my_bot.create_thread(
#    "This is the start of a thread!", # posts[0] -> Root
#    "This is the first reply.",       # posts[1] -> Parent: Root
#    "This is the second reply.",      # posts[2] -> Parent: posts[1]
#    "And the final word."             # posts[3] -> Parent: posts[2]
#)
