from django.core.management.base import BaseCommand
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from django.conf import settings
from collections import Counter


class Command(BaseCommand):
    help = "Analyze rejected tags from the CSV log"

    def create_visualizations(self, df, word_counts):
        """Create and save visualization plots"""
        # Set style
        plt.style.use("seaborn")

        # Create plots directory
        plots_dir = settings.BASE_DIR / "logs" / "plots"
        plots_dir.mkdir(exist_ok=True)

        # 1. Pie chart of rejection reasons
        plt.figure(figsize=(10, 6))
        reason_counts = df["reason"].value_counts()
        plt.pie(reason_counts.values, labels=reason_counts.index, autopct="%1.1f%%")
        plt.title("Tag Rejection Reasons")
        plt.savefig(plots_dir / "rejection_reasons_pie.png")
        plt.close()

        # 2. Bar plot of top rejected tags by post count
        plt.figure(figsize=(12, 6))
        top_rejected = df.nlargest(15, "post_count")
        sns.barplot(data=top_rejected, x="post_count", y="tag_name")
        plt.title("Top 15 Rejected Tags by Post Count")
        plt.xlabel("Post Count")
        plt.ylabel("Tag Name")
        plt.tight_layout()
        plt.savefig(plots_dir / "top_rejected_tags.png")
        plt.close()

        # 3. Bar plot of most common unknown words
        plt.figure(figsize=(12, 6))
        word_df = pd.DataFrame(word_counts.most_common(20), columns=["word", "count"])
        sns.barplot(data=word_df, x="count", y="word")
        plt.title("Most Common Unknown Words")
        plt.xlabel("Frequency")
        plt.ylabel("Word")
        plt.tight_layout()
        plt.savefig(plots_dir / "common_unknown_words.png")
        plt.close()

        # 4. Post count distribution
        plt.figure(figsize=(10, 6))
        sns.histplot(data=df, x="post_count", bins=50, log_scale=True)
        plt.title("Distribution of Rejected Tags Post Counts")
        plt.xlabel("Post Count (log scale)")
        plt.ylabel("Frequency")
        plt.tight_layout()
        plt.savefig(plots_dir / "post_count_distribution.png")
        plt.close()

        print(f"\nVisualizations saved to {plots_dir}/")

    def handle(self, *args, **options):
        log_file = settings.BASE_DIR / "logs" / "rejected_tags.csv"
        if not log_file.exists():
            print("No rejected tags log found")
            return

        df = pd.read_csv(log_file)

        # Overall statistics
        print("\n=== Rejection Statistics ===")
        print(f"Total rejected tags: {len(df)}")
        print("\nRejection reasons:")
        print(df["reason"].value_counts())

        # High post-count rejections
        print("\n=== High Post Count Rejections ===")
        high_count = df.nlargest(10, "post_count")
        for _, row in high_count.iterrows():
            print(f"{row['tag_name']} ({row['post_count']} posts) - {row['reason']}")

        # Common unknown words
        print("\n=== Common Unknown Words ===")
        unknown = df[df["reason"] == "unknown_words"]
        words = [
            word.strip()
            for details in unknown["details"].str.split("Words: ")
            for word in details[1].split(",")
        ]
        word_counts = Counter(words)
        print("\nMost common unknown words:")
        for word, count in word_counts.most_common(20):
            print(f"{word}: {count} times")

        # Create visualizations
        self.create_visualizations(df, word_counts)
