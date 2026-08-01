"""
Elasticsearch Service

Provides full-text search, filtering, and faceted queries for job listings.
Uses AsyncElasticsearch for non-blocking operations.
Falls back gracefully when Elasticsearch is not available.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy import - elasticsearch is optional
_es_client = None
_es_available = False

INDEX_NAME = "cybershield_jobs"

JOB_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "job_analyzer": {
                    "type": "standard",
                    "stopwords": "_english_",
                }
            }
        },
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "job_analyzer",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "company_name": {"type": "keyword"},
            "location": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "country": {"type": "keyword"},
            "city": {"type": "keyword"},
            "description": {"type": "text", "analyzer": "job_analyzer"},
            "url": {"type": "keyword", "index": False},
            "source": {"type": "keyword"},
            "salary_min": {"type": "float"},
            "salary_max": {"type": "float"},
            "salary_currency": {"type": "keyword"},
            "is_remote": {"type": "boolean"},
            "is_hybrid": {"type": "boolean"},
            "is_onsite": {"type": "boolean"},
            "job_type": {"type": "keyword"},
            "experience_level": {"type": "keyword"},
            "required_skills": {"type": "keyword"},
            "preferred_skills": {"type": "keyword"},
            "posting_date": {"type": "date"},
            "created_at": {"type": "date"},
        }
    },
}


async def init_elasticsearch(host: str = "http://localhost:9200") -> bool:
    """Initialize Elasticsearch client and create index if needed."""
    global _es_client, _es_available

    try:
        from elasticsearch import AsyncElasticsearch

        _es_client = AsyncElasticsearch(hosts=[host], request_timeout=10)

        # Check if ES is reachable
        if await _es_client.ping():
            _es_available = True
            logger.info(f"Elasticsearch connected: {host}")

            # Create index if it doesn't exist
            if not await _es_client.indices.exists(index=INDEX_NAME):
                await _es_client.indices.create(index=INDEX_NAME, body=JOB_MAPPING)
                logger.info(f"Created Elasticsearch index: {INDEX_NAME}")

            return True
        else:
            logger.warning("Elasticsearch ping failed - search will use database fallback")
            return False

    except ImportError:
        logger.info("elasticsearch package not installed - search will use database fallback")
        return False
    except Exception as e:
        logger.warning(
            f"Elasticsearch initialization failed: {e} - search will use database fallback"
        )
        return False


async def close_elasticsearch():
    """Close Elasticsearch client connection."""
    global _es_client, _es_available
    if _es_client:
        try:
            await _es_client.close()
        except Exception as e:
            logger.debug(f"Error closing Elasticsearch client: {e}")
        _es_client = None
        _es_available = False


def is_available() -> bool:
    """Check if Elasticsearch is available."""
    return _es_available


async def index_job(job_data: Dict[str, Any]) -> bool:
    """Index a single job document."""
    if not _es_available or not _es_client:
        return False

    try:
        doc_id = job_data.get("id") or job_data.get("source_id")
        if not doc_id:
            return False

        await _es_client.index(
            index=INDEX_NAME,
            id=str(doc_id),
            document=job_data,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to index job {job_data.get('id')}: {e}")
        return False


async def index_jobs(jobs: List[Dict[str, Any]]) -> int:
    """Bulk index multiple job documents. Returns count of successfully indexed."""
    if not _es_available or not _es_client or not jobs:
        return 0

    try:
        from elasticsearch.helpers import async_bulk

        actions = []
        for job in jobs:
            doc_id = job.get("id") or job.get("source_id")
            if doc_id:
                actions.append(
                    {
                        "_index": INDEX_NAME,
                        "_id": str(doc_id),
                        "_source": job,
                    }
                )

        if actions:
            success, _ = await async_bulk(_es_client, actions)
            logger.info(f"Indexed {success} jobs into Elasticsearch")
            return success
        return 0
    except Exception as e:
        logger.error(f"Bulk index failed: {e}")
        return 0


async def search_jobs(
    query: Optional[str] = None,
    company: Optional[str] = None,
    country: Optional[str] = None,
    location: Optional[str] = None,
    skills: Optional[List[str]] = None,
    job_type: Optional[str] = None,
    experience_level: Optional[str] = None,
    is_remote: Optional[bool] = None,
    min_salary: Optional[float] = None,
    max_salary: Optional[float] = None,
    sort_by: str = "_score",
    sort_order: str = "desc",
    skip: int = 0,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Search jobs using Elasticsearch with full-text search and filters.

    Returns:
        Dict with 'results', 'total', 'aggregations'
    """
    if not _es_available or not _es_client:
        return {"results": [], "total": 0, "aggregations": {}, "source": "database"}

    try:
        must_clauses: List[Dict[str, Any]] = []
        filter_clauses: List[Dict[str, Any]] = []

        # Full-text search on title and description
        if query:
            must_clauses.append(
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^3", "description^2", "company_name", "required_skills^2"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                }
            )
        else:
            must_clauses.append({"match_all": {}})

        # Exact filters
        if company:
            filter_clauses.append({"term": {"company_name": company}})
        if country:
            filter_clauses.append({"term": {"country": country}})
        if location:
            filter_clauses.append({"match": {"location": location}})
        if job_type:
            filter_clauses.append({"term": {"job_type": job_type}})
        if experience_level:
            filter_clauses.append({"term": {"experience_level": experience_level}})
        if is_remote is not None:
            filter_clauses.append({"term": {"is_remote": is_remote}})

        # Skills filter (matches if document contains ANY of the specified skills)
        if skills:
            filter_clauses.append({"terms": {"required_skills": skills}})

        # Salary range filter
        salary_range: Dict[str, float] = {}
        if min_salary is not None:
            salary_range["gte"] = min_salary
        if max_salary is not None:
            salary_range["lte"] = max_salary
        if salary_range:
            filter_clauses.append({"range": {"salary_min": salary_range}})

        # Build query
        es_query = {
            "bool": {
                "must": must_clauses,
                "filter": filter_clauses,
            }
        }

        # Sort
        sort = [{sort_by: {"order": sort_order}}]

        # Execute search
        response = await _es_client.search(
            index=INDEX_NAME,
            query=es_query,
            sort=sort,
            from_=skip,
            size=limit,
            aggs={
                "by_company": {"terms": {"field": "company_name", "size": 10}},
                "by_country": {"terms": {"field": "country", "size": 10}},
                "by_job_type": {"terms": {"field": "job_type", "size": 5}},
                "by_skills": {"terms": {"field": "required_skills", "size": 20}},
                "salary_stats": {"stats": {"field": "salary_min"}},
            },
        )

        # Extract results
        hits = response["hits"]
        results = [hit["_source"] for hit in hits["hits"]]

        aggregations: Dict[str, Any] = {}
        if "aggregations" in response:
            for agg_name, agg_data in response["aggregations"].items():
                if "buckets" in agg_data:
                    aggregations[agg_name] = [
                        {"key": b["key"], "count": b["doc_count"]} for b in agg_data["buckets"]
                    ]
                elif "value" in agg_data:
                    aggregations[agg_name] = agg_data

        return {
            "results": results,
            "total": hits["total"]["value"],
            "aggregations": aggregations,
            "source": "elasticsearch",
        }

    except Exception as e:
        logger.error(f"Elasticsearch search failed: {e}")
        return {"results": [], "total": 0, "aggregations": {}, "source": "error"}


async def delete_job(job_id: str) -> bool:
    """Delete a job from the index."""
    if not _es_available or not _es_client:
        return False

    try:
        await _es_client.delete(index=INDEX_NAME, id=str(job_id))
        return True
    except Exception:
        return False


async def get_index_stats() -> Dict[str, Any]:
    """Get index statistics."""
    if not _es_available or not _es_client:
        return {"available": False}

    try:
        stats = await _es_client.indices.stats(index=INDEX_NAME)
        doc_count = stats["indices"][INDEX_NAME]["total"]["docs"]["count"]
        return {
            "available": True,
            "index": INDEX_NAME,
            "document_count": doc_count,
        }
    except Exception:
        return {"available": True, "index": INDEX_NAME, "document_count": -1}
