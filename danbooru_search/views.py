import csv
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import os
from django.conf import settings


def search_page(request):
    """Renders the search page"""
    return render(request, "search.html")


def search_csv(request):
    """API endpoint to search the CSV file"""
    query = request.GET.get("q", "").lower()
    results = []

    if query:
        csv_path = os.path.join(settings.BASE_DIR, "danbooru_tags.csv")
        with open(csv_path, "r", encoding="utf-8") as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                # Assuming the CSV has 'tag' column - adjust field name if different
                if query in row["tag"].lower():
                    results.append(row)
                    if len(results) >= 50:  # Limit results to 50 matches
                        break

    return JsonResponse({"results": results})
