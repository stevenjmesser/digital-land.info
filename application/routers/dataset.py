import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from starlette.responses import JSONResponse

from application.data_access.digital_land_queries import (
    get_dataset_query,
    get_datasets,
    get_latest_resource,
    get_publisher_coverage,
)

from application.data_access.entity_queries import get_entity_count
from application.core.templates import templates
from application.core.utils import DigitalLandJSONResponse
from application.search.enum import Suffix
from application.settings import get_settings, Settings

router = APIRouter()
logger = logging.getLogger(__name__)


def list_datasets(request: Request, extension: Optional[Suffix] = None):
    datasets = get_datasets()
    entity_counts_response = get_entity_count()
    entity_counts = {count[0]: count[1] for count in entity_counts_response}
    # add entity count if available
    for dataset in datasets:
        count = (
            entity_counts.get(dataset.dataset)
            if entity_counts.get(dataset.dataset)
            else 0
        )
        dataset.entity_count = count

    themes = {}

    for ds in (d for d in datasets if d.themes):
        for theme in ds.themes:
            themes.setdefault(theme, {"dataset": []})
            if ds.entity_count > 0:
                themes[theme]["dataset"].append(ds)

    data = {"datasets": datasets, "themes": themes}
    if extension is not None and extension.value == "json":
        return JSONResponse(data)
    else:
        return templates.TemplateResponse(
            "dataset_index.html", {"request": request, **data}
        )


def get_dataset(
    request: Request,
    dataset: str,
    limit: int = 50,
    settings: Settings = Depends(get_settings),
):
    collection_bucket = settings.S3_COLLECTION_BUCKET
    try:
        _dataset = get_dataset_query(dataset)
        entity_count = get_entity_count(dataset)
        latest_resource = get_latest_resource(dataset)
        publisher_coverage = get_publisher_coverage(dataset)

        return templates.TemplateResponse(
            "dataset.html",
            {
                "request": request,
                "dataset": _dataset,
                "collection_bucket": collection_bucket,
                "entity_count": entity_count[1] if entity_count else 0,
                "publishers": {
                    "expected": publisher_coverage.expected_publisher_count,
                    "current": publisher_coverage.publisher_count,
                },
                "latest_resource": latest_resource,
                "last_collection_attempt": latest_resource.last_collection_attempt
                if latest_resource
                else None,
            },
        )
    except KeyError as e:
        logger.exception(e)
        return templates.TemplateResponse(
            "dataset-backlog.html",
            {
                "request": request,
                "name": dataset.replace("-", " ").capitalize(),
            },
        )


router.add_api_route(
    ".{extension}",
    endpoint=list_datasets,
    response_class=DigitalLandJSONResponse,
    tags=["List datasets"],
)
router.add_api_route(
    "/", endpoint=list_datasets, response_class=HTMLResponse, include_in_schema=False
)

router.add_api_route(
    "/{dataset}.{extension}",
    endpoint=get_dataset,
    response_class=DigitalLandJSONResponse,
    tags=["Get dataset"],
)
router.add_api_route(
    "/{dataset}",
    endpoint=get_dataset,
    response_class=HTMLResponse,
    include_in_schema=False,
)
