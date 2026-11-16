import string
from pathlib import Path

import pandas as pd
import pytest

from src import MovieStorage
import main


def test_movies_persist(client, test_storage, uploaded_movies):
    reopened = MovieStorage(test_storage.db_path)
    df = reopened.get()

    original_titles = pd.read_csv(Path("fixtures") / "sample_movies.csv")["title"].tolist()
    assert reopened.count_movies() == 20
    assert len(df) == 20
    assert list(df.columns) == ["title", "release_year", "rating", "genre"]
    assert df["title"].tolist() == original_titles

    stored_ids = [row["id"] for row in reopened.select_columns(["title"], limit=100)]
    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200
    api_ids = [row["id"] for row in response.json()["data"]]

    assert stored_ids == list(range(1, 21))
    assert api_ids == list(range(1, 21))


def test_cache_and_processing(client, uploaded_movies, processing_body):
    # TODO 1: first retrievals are cached under their own limits
    full = client.get("/movies", params={"limit": 100})
    one = client.get("/movies", params={"limit": 1})
    assert full.status_code == 200
    assert one.status_code == 200
    assert main.cache.get(100) == full.json()
    assert main.cache.get(1) == one.json()

    # TODO 2: a repeat retrieval returns the same response
    repeat = client.get("/movies", params={"limit": 100})
    assert repeat.status_code == 200
    assert repeat.json() == full.json()

    # TODO 3: processing succeeds and clears every cached limit
    processed = client.post("/movies/process", json=processing_body)
    assert processed.status_code == 200
    body = processed.json()
    assert body["validation_rows_removed"] == 0
    report = body["cleaning_report"]
    assert report["rows_before"] == 20
    assert report["rows_after"] == 16
    assert report["rows_removed"] == 4
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    # TODO 4: the next retrieval reads the 16 processed rows and is cached
    after = client.get("/movies", params={"limit": 100})
    assert after.status_code == 200
    data = after.json()
    assert data["total_rows"] == 16
    expected_titles = [f"Movie {letter}" for letter in string.ascii_uppercase[:16]]
    assert [movie["title"] for movie in data["data"]] == expected_titles
    assert [movie["id"] for movie in data["data"]] == list(range(1, 17))
    assert main.cache.get(100) == data


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    # TODO 1: populate the cache
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200

    # TODO 2: any database read now fails the test
    def fail_if_called(*args, **kwargs):
        pytest.fail("The database was queried even though the response was cached")

    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)

    # TODO 3: the repeat request is served from the cache
    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == first.json()