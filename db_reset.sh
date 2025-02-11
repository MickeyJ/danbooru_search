rm db.sqlite3
rm -rf danbooru_search/migrations/0*.py
python manage.py makemigrations
python manage.py migrate