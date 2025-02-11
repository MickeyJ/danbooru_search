import csv
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import os
from django.conf import settings
import requests
from datetime import datetime
import time
from asgiref.sync import sync_to_async, async_to_sync
from concurrent.futures import ThreadPoolExecutor
import threading
import asyncio
import aiohttp
from django.db import transaction
from .models import Tag, UpdateStatus, CommonWord
from django.views.decorators.csrf import csrf_exempt  # Temporary for testing
from django.views.decorators.http import require_http_methods
import ssl
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count
from Levenshtein import distance  # You'll need to pip install python-Levenshtein
from django.core.management import call_command

# Global task state
update_task = None
update_thread = None


def search_page(request):
    """Renders the search page"""
    return render(request, "search.html")


def search_csv(request):
    """API endpoint to search tags"""
    query = request.GET.get("q", "").lower()
    results = []

    if query:
        # More efficient database search
        tags = Tag.objects.filter(name__istartswith=query).order_by("-post_count")[:50]

        results = [{"tag": tag.name, "times_used": tag.post_count} for tag in tags]

    return JsonResponse({"results": results})


async def start_background_task():
    """Starts the update process in a way that won't be cancelled"""
    try:
        # Check if update is already running
        if cache.get("tag_update_running"):
            print("Update already in progress...")
            return

        # Set update flag
        cache.set("tag_update_running", True, timeout=3600)  # 1 hour timeout

        try:
            await perform_update()
        finally:
            # Clear update flag when done
            cache.delete("tag_update_running")

    except Exception as e:
        print(f"Background task error: {str(e)}")


def run_async_update():
    """Run the async update in a separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(perform_update())
    finally:
        loop.close()


@csrf_exempt
@require_http_methods(["POST"])
def update_tags(request):
    """Initiates async tag update process"""
    global update_thread

    try:
        # Check if update is already running
        if update_thread and update_thread.is_alive():
            return JsonResponse(
                {"success": False, "message": "Update already in progress"}
            )

        # Start new update thread
        update_thread = threading.Thread(target=run_async_update)
        update_thread.daemon = True
        update_thread.start()

        return JsonResponse(
            {
                "success": True,
                "message": "Tag update started. This may take several minutes.",
            }
        )

    except Exception as e:
        print(f"Update error: {str(e)}")
        return JsonResponse({"success": False, "message": str(e)}, status=500)


async def get_letter_distribution(tag_count=None):
    """Get tag distribution by first letter"""
    letter_stats = await sync_to_async(
        lambda: {
            letter: Tag.objects.filter(name__istartswith=letter).count()
            for letter in "abcdefghijklmnopqrstuvwxyz"
        }
    )()

    other_count = await sync_to_async(
        lambda: Tag.objects.exclude(name__regex=r"^[a-zA-Z]").count()
    )()

    if tag_count is None:
        tag_count = sum(letter_stats.values()) + other_count

    print("\nTag Distribution by First Letter:")
    print("=" * 40)

    if tag_count == 0:
        print("No tags in database yet")
        for letter in "abcdefghijklmnopqrstuvwxyz":
            print(f"{letter.upper()}: 0 (0.0%)")
        print("Other: 0 (0.0%)")
    else:
        for letter in "abcdefghijklmnopqrstuvwxyz":
            count = letter_stats[letter]
            percentage = (count / tag_count) * 100 if tag_count > 0 else 0
            print(f"{letter.upper()}: {count:,} ({percentage:.1f}%)")

        percentage = (other_count / tag_count) * 100 if tag_count > 0 else 0
        print(f"Other: {other_count:,} ({percentage:.1f}%)")

    print("=" * 40)

    return letter_stats, other_count


def is_valid_tag(name):
    """Check if a tag name is valid"""
    # Tag should be reasonable length (e.g., less than 100 chars)
    # if len(name) > 150:
    #     return False

    # Tag should contain at least one letter or number
    # if not any(c.isalnum() for c in name):
    #     return False

    # Tag should only contain allowed characters
    # allowed_chars = set(
    #     "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-()."
    # )
    # if not all(c in allowed_chars for c in name):
    #     return False

    return True


def is_likely_typo(word, common_words, max_distance=1):
    """
    Check if a word is likely a typo based on Levenshtein distance
    to common words. Returns (is_typo, suggested_word) tuple.
    """
    # Skip very short words as they're more likely to be valid abbreviations
    if len(word) <= 2:
        return False, None

    # Only check for very obvious typos with repeated letters
    if any(
        c * 3 in word for c in "abcdefghijklmnopqrstuvwxyz"
    ):  # Three or more of same letter
        return True, None

    # If the word exists in our dictionary, it's valid
    if word in common_words:
        return False, None

    # If we get here, the word isn't in our dictionary
    return True, None


async def perform_update():
    """Background task to update tags"""
    try:
        # Check if word database is empty
        if await sync_to_async(CommonWord.objects.count)() == 0:
            print("Initializing word database...")
            await sync_to_async(lambda: call_command("init_wordlist"))()

        # First, check for duplicates before we start
        print("\n=== Checking for Existing Duplicates ===")
        duplicates = await sync_to_async(
            lambda: list(
                Tag.objects.values("name")
                .annotate(count=Count("id"))
                .filter(count__gt=1)
            )
        )()

        if duplicates:
            print("\n!!! EXISTING DUPLICATES FOUND !!!")
            print("=" * 40)
            for dup in duplicates:
                print(f"Tag: {dup['name']}, Count: {dup['count']}")
            print("=" * 40)
            print("You should clean up duplicates before continuing.")
            return  # Stop the update if duplicates exist
        else:
            print("No duplicates found - safe to proceed with update.")

        # Show initial database statistics
        print("\n=== Current Database Statistics ===")
        initial_tag_count = await sync_to_async(Tag.objects.count)()
        print(f"Total tags: {initial_tag_count}")

        # Get initial distribution
        initial_letter_stats, initial_other = await get_letter_distribution(
            initial_tag_count
        )

        # Initialize or get update status
        status = await sync_to_async(lambda: UpdateStatus.objects.first())()
        if not status:
            status = await sync_to_async(UpdateStatus.objects.create)()

        # Create backup before starting
        if not status.last_backup or (timezone.now() - status.last_backup).days >= 1:
            await sync_to_async(_create_backup)()
            status.last_backup = timezone.now()
            await sync_to_async(lambda: status.save())()

        # Initialize with a reasonable estimate of total tags
        status.total_tags = 200000  # Approximate number of tags
        status.start_time = timezone.now()
        status.is_updating = True
        await sync_to_async(lambda: status.save())()

        tags_per_page = 1000
        total_tags_processed = 0

        # Get the last successful page
        last_page = await sync_to_async(
            lambda: Tag.objects.first().last_update_page if Tag.objects.exists() else 0
        )()
        page = last_page + 1

        print("\n=== Starting Tag Database Update ===")
        print(
            f"Resuming from page {page}" if last_page > 0 else "Starting fresh update"
        )
        print(f"Fetching tags in batches of {tags_per_page}")

        # Create SSL context for HTTPS requests
        ssl_context = ssl.create_default_context()

        timeout = aiohttp.ClientTimeout(total=60)  # 60 second timeout

        async def check_duplicates():
            """Check and report any duplicate tags"""
            print("\n=== Checking for Duplicates ===")
            duplicates = await sync_to_async(
                lambda: list(
                    Tag.objects.values("name")
                    .annotate(count=Count("id"))
                    .filter(count__gt=1)
                )
            )()

            if duplicates:
                print("\n!!! DUPLICATE TAGS FOUND !!!")
                print("=" * 40)
                for dup in duplicates:
                    print(f"Tag: {dup['name']}, Count: {dup['count']}")
                print("=" * 40)
                print("Consider cleaning up these duplicates.")
            else:
                print("No duplicates found.")
            return bool(duplicates)

        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_context), timeout=timeout
        ) as session:
            retry_count = 0
            max_retries = 5

            while True:
                try:
                    url = "https://danbooru.donmai.us/tags.json"
                    params = {
                        "page": page,  # Keep using numeric pages
                        "limit": tags_per_page,
                        "search[order]": "id_asc",  # Use explicit ascending ID order
                    }

                    # Build and log the full URL with parameters
                    param_string = "&".join(f"{k}={v}" for k, v in params.items())
                    full_url = f"{url}?{param_string}"
                    print(f"\nRequesting: {full_url}")

                    print(f"Fetching page {page}...")
                    async with session.get(url, params=params, timeout=30) as response:
                        if response.status == 410:
                            print("\nReached end of tags")
                            break
                        elif response.status != 200:
                            raise Exception(f"API returned status {response.status}")
                        tags = await response.json()

                    if not tags:
                        print("\nNo more tags to fetch")
                        break

                    batch_size = len(tags)
                    total_tags_processed += batch_size

                    # Collect tags for bulk update
                    new_tags = []
                    invalid_tags = []
                    deprecated_count = 0
                    typo_count = 0

                    # Load common words from database
                    common_words = set(
                        await sync_to_async(
                            lambda: list(
                                CommonWord.objects.values_list("word", flat=True)
                            )
                        )()
                    )

                    for tag_data in tags:
                        if tag_data.get("is_deprecated", False):
                            deprecated_count += 1
                            continue

                        # Check for typos and known words
                        has_known_word = False
                        has_typo = False

                        if "words" in tag_data:
                            for word in tag_data["words"]:
                                word = word.lower()
                                is_typo, _ = is_likely_typo(word, common_words)
                                if is_typo:
                                    has_typo = True
                                    break
                                elif word in common_words:
                                    has_known_word = True

                        # Skip if there's a typo or if no words are known
                        if has_typo or (tag_data["words"] and not has_known_word):
                            typo_count += 1
                            continue

                        if is_valid_tag(tag_data["name"]):
                            new_tags.append(
                                Tag(
                                    name=tag_data["name"],
                                    post_count=tag_data["post_count"],
                                )
                            )
                        else:
                            invalid_tags.append(tag_data["name"])

                    if deprecated_count:
                        print(f"Skipped {deprecated_count} deprecated tags")
                    if typo_count:
                        print(f"Skipped {typo_count} tags with possible typos")

                    if invalid_tags:
                        print(f"\n!!! Found {len(invalid_tags)} invalid tags !!!")
                        print("Sample of invalid tags:")
                        for tag in invalid_tags[:5]:
                            print(f"- {tag}")
                        print("\nStopping update process due to invalid tags")
                        print("This might indicate an API issue")
                        return  # Stop the entire update process

                    # Save this page's tags
                    if new_tags:
                        print(f"\nSaving {len(new_tags)} valid tags to database...")
                        await sync_to_async(_bulk_update_tags)(new_tags)
                        print("Batch saved successfully")

                    # Update last successful page
                    await sync_to_async(_update_last_page)(page)

                    # Check actual database count after each page
                    await get_actual_count()

                    print(f"Total tags processed so far: {total_tags_processed}")
                    print("Waiting 1 second before next request (API rate limiting)")
                    await asyncio.sleep(1)
                    page += 1

                    status.processed_tags += batch_size
                    status.current_page = page

                    # Calculate and log progress
                    percentage = status.progress_percentage
                    remaining = status.estimated_time_remaining

                    print(f"\nProgress: {percentage:.1f}%")
                    if remaining:
                        hours = int(remaining // 3600)
                        minutes = int((remaining % 3600) // 60)
                        print(f"Estimated time remaining: {hours}h {minutes}m")

                    await sync_to_async(lambda: status.save())()

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        print(
                            f"\nFailed after {max_retries} retries. Preserving current data."
                        )
                        return  # Don't raise the exception, just exit

                    wait_time = min(2**retry_count, 60)
                    print(f"\nError: {str(e)}")
                    print(
                        f"Retry {retry_count}/{max_retries} in {wait_time} seconds..."
                    )
                    await asyncio.sleep(wait_time)
                    continue

            # Final batch
            if new_tags:
                print(f"\nSaving final batch of {len(new_tags)} tags...")
                await sync_to_async(_bulk_update_tags)(new_tags)
                print("Final batch saved successfully")

            # Final duplicate check
            print("\nPerforming final duplicate check...")
            has_duplicates = await check_duplicates()
            if not has_duplicates:
                print("No duplicates found - database is clean!")

            print("\n=== Tag Database Update Complete ===")
            print(f"Total tags processed: {total_tags_processed}")
            print("Database is now up to date!")

            # At the end, verify the changes
            final_tag_count = await sync_to_async(Tag.objects.count)()
            print("\n=== Update Statistics ===")
            print(f"Initial tag count: {initial_tag_count}")
            print(f"Final tag count: {final_tag_count}")
            print(f"Tags added/updated: {total_tags_processed}")
            print(f"Net change in database: {final_tag_count - initial_tag_count}")

            if final_tag_count < initial_tag_count:
                print("\nWARNING: Tag count decreased - this might indicate an issue!")

            # Show final distribution with changes
            print("\n=== Final Letter Distribution ===")
            final_letter_stats, final_other = await get_letter_distribution(
                final_tag_count
            )

            # Show changes
            print("\nChanges in Distribution:")
            print("=" * 40)
            for letter in "abcdefghijklmnopqrstuvwxyz":
                initial = initial_letter_stats[letter]
                final = final_letter_stats[letter]
                diff = final - initial
                if diff != 0:  # Only show letters that changed
                    print(f"{letter.upper()}: {'+'if diff > 0 else ''}{diff:,} change")

            diff = final_other - initial_other
            if diff != 0:
                print(f"Other: {'+'if diff > 0 else ''}{diff:,} change")
            print("=" * 40)

    except Exception as e:
        print("\n!!! Tag Update Failed !!!")
        print(f"Error: {str(e)}")
        print("\nPreserving current data - backup restoration skipped")
        # Don't restore backup automatically
        return


@transaction.atomic
def _bulk_update_tags(tags_to_update):
    """Bulk create new tags only"""
    Tag.objects.bulk_create(
        tags_to_update,
        ignore_conflicts=True,  # Skip any existing tags without updating them
    )


@transaction.atomic
def _update_last_page(page_number):
    """Update the last successful page number"""
    if Tag.objects.exists():
        Tag.objects.all().update(last_update_page=page_number)


def benchmark_search(request):
    """Compare CSV vs DB search performance"""
    query = "girl"  # Example search term
    results = []

    # CSV Search
    csv_start = time.time()
    with open("danbooru_tags.csv", "r") as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            if query in row["tag"].lower():
                results.append(row)
                if len(results) >= 50:
                    break
    csv_time = time.time() - csv_start

    # DB Search
    db_start = time.time()
    tags = Tag.objects.filter(name__istartswith=query).order_by("-post_count")[:50]
    db_results = [{"tag": tag.name, "times_used": tag.post_count} for tag in tags]
    db_time = time.time() - db_start

    return JsonResponse(
        {
            "csv_time": csv_time,
            "db_time": db_time,
            "speedup": f"{csv_time/db_time:.1f}x faster",
        }
    )


def _create_backup():
    """Create a backup of the database"""
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    backup_path = settings.BASE_DIR / "backups"
    backup_path.mkdir(exist_ok=True)

    # Get current tag count
    tag_count = Tag.objects.count()

    backup_file = backup_path / f"db_backup_{timestamp}_{tag_count}_tags.sqlite3"

    # Copy current database to backup
    import shutil

    shutil.copy2(settings.DATABASES["default"]["NAME"], backup_file)
    print(f"\nBackup created: {backup_file} ({tag_count:,} tags)")


def _restore_backup():
    """Restore the most recent backup, but only if it has more tags than current DB"""
    backup_path = settings.BASE_DIR / "backups"
    if not backup_path.exists():
        print("\nNo backup directory found")
        return False

    current_count = Tag.objects.count()
    print(f"\nCurrent database has {current_count:,} tags")

    backups = []
    for backup in backup_path.glob("db_backup_*.sqlite3"):
        try:
            # Extract tag count from filename
            tag_count = int(backup.stem.split("_")[-2])
            backups.append((backup, tag_count))
        except (ValueError, IndexError):
            continue

    if not backups:
        print("\nNo valid backups found")
        return False

    # Sort by tag count, then by timestamp
    latest_backup, backup_count = max(
        backups, key=lambda x: (x[1], x[0].stat().st_mtime)
    )

    if backup_count < current_count:
        print(
            f"\nSkipping backup restoration - current database ({current_count:,} tags) "
            + f"has more tags than backup ({backup_count:,} tags)"
        )
        return False

    print(f"\nRestoring from backup: {latest_backup} ({backup_count:,} tags)")

    import shutil

    shutil.copy2(latest_backup, settings.DATABASES["default"]["NAME"])
    return True


async def get_actual_count():
    """Get actual count of tags in database"""
    count = await sync_to_async(Tag.objects.count)()
    print(f"\nActual tags in database: {count:,}")

    # Get sample of most recently added tags (using ID instead of created_at)
    recent_tags = await sync_to_async(
        lambda: list(Tag.objects.order_by("-id")[:5].values("name", "post_count"))
    )()
    print("\nMost recently added tags:")  # Changed wording to be more accurate
    for tag in recent_tags:
        print(f"- {tag['name']} ({tag['post_count']:,} posts)")
