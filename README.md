# MP3 Movie API

This FastAPI application stores a single movie collection in SQLite and serves it through a small REST API. `POST /upload` reads a CSV, checks that it has exactly the `title`, `release_year`, `rating`, and `genre` columns and at least one row, and replaces the stored collection through `MovieStorage` in `src/storage.py`. `src/database.py` creates the SQLite connection and the `movies` table, so the data in `data/movies.db` survives server restarts. `GET /movies/search` filters and sorts movies with SQL, while `POST /movies/process` reuses the MP1 functions in `data_pipeline/` to validate, deduplicate, handle missing values, and remove outliers before saving the cleaned rows back to SQLite. `GET /movies` responses are cached for 90 seconds by `MovieCache` in `src/cache.py`, which uses FakeRedis and keys each entry by the requested limit. Every successful upload or processing run invalidates the whole cache, so later retrievals always reflect the current database. Pydantic models in `src/models.py` define the request and response shapes, and `src/middleware.py` and `src/utils.py` handle request logging and logging setup.

## Running the API

```bash
python -m uvicorn main:app --reload
```

Then open http://127.0.0.1:8000/docs.

## Running the tests

```bash
python -m pytest tests -v
```

## Sample processing request

After uploading `fixtures/sample_movies.csv`, send this body to `POST /movies/process`:

```json
{
  "validation": {
    "required_columns": ["title", "release_year", "rating", "genre"],
    "numeric_columns": ["release_year", "rating"]
  },
  "processing": {
    "remove_duplicates": true,
    "missing": {"enabled": true, "axis": "rows"},
    "outliers": {
      "enabled": true,
      "columns": ["rating"],
      "method": "iqr",
      "threshold": 1.5
    }
  }
}
```

Expected result:

```json
{
  "validation_rows_removed": 0,
  "cleaning_report": {
    "rows_before": 20,
    "rows_after": 16,
    "rows_removed": 4,
    "columns_before": 4,
    "columns_after": 4,
    "columns_removed": 0
  }
}
```
