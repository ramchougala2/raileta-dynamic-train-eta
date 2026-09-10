from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# CONFIG
# ============================================================

APP_NAME = "RAILETA Backend"
RAILRADAR_BASE = "https://api.railradar.in"
IST = ZoneInfo("Asia/Kolkata")


app = FastAPI(
    title=APP_NAME,
    version="5.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# BASIC HELPERS
# ============================================================

def today_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def safe_number(value: Any) -> float | None:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_status(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("_", "-")
    )


def is_not_started(value: Any) -> bool:
    return normalize_status(value) in {
        "not-started",
        "not started",
        "scheduled",
        "yet-to-start",
        "yet to start",
    }


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return None


def format_time(value: Any) -> str | None:
    dt = parse_datetime(value)

    if dt is None:
        return None

    return dt.astimezone(IST).strftime("%H:%M")


def format_datetime(value: Any) -> str | None:
    dt = parse_datetime(value)

    if dt is None:
        return None

    return dt.astimezone(IST).strftime(
        "%d-%b-%Y %H:%M:%S"
    )


def add_minutes(
    value: Any,
    minutes: float | int | None,
) -> str | None:
    dt = parse_datetime(value)

    if dt is None:
        return None

    if minutes is None:
        return None

    result = (
        dt
        + timedelta(
            minutes=float(minutes)
        )
    )

    return result.astimezone(IST).isoformat()


def first_value(
    obj: dict[str, Any],
    keys: list[str],
) -> Any:
    for key in keys:
        if key in obj:
            value = obj.get(key)

            if value not in (
                None,
                "",
            ):
                return value

    return None


# ============================================================
# API KEY
# ============================================================

def get_api_key() -> str:
    key = os.getenv(
        "RAILRADAR_API_KEY",
        "",
    ).strip()

    if not key:
        raise HTTPException(
            status_code=500,
            detail=(
                "RAILRADAR_API_KEY is not configured."
            ),
        )

    return key


# ============================================================
# RAILRADAR REQUEST
# ============================================================

def railradar_get(
    path: str,
    params: dict[str, Any] | None = None,
) -> Any:

    url = (
        f"{RAILRADAR_BASE}"
        f"{path}"
    )

    headers = {
        "Authorization": (
            f"Bearer {get_api_key()}"
        ),
        "Accept": "application/json",
        "User-Agent": "RAILETA/5.0",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params or {},
            timeout=25,
        )

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "RailRadar connection failed: "
                f"{exc}"
            ),
        ) from exc

    try:
        payload = response.json()

    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "RailRadar returned invalid JSON."
            ),
        ) from exc

    if not response.ok:

        error = (
            payload.get("error")
            if isinstance(
                payload,
                dict,
            )
            else None
        )

        message = (
            error.get("message")
            if isinstance(
                error,
                dict,
            )
            else None
        )

        raise HTTPException(
            status_code=response.status_code,
            detail=(
                message
                or f"RailRadar HTTP {response.status_code}"
            ),
        )

    if isinstance(
        payload,
        dict,
    ):

        if payload.get("success") is False:

            error = (
                payload.get("error")
                or {}
            )

            raise HTTPException(
                status_code=502,
                detail=(
                    error.get(
                        "message",
                        "RailRadar request failed.",
                    )
                ),
            )

        return payload.get(
            "data",
            payload,
        )

    return payload


# ============================================================
# LIVE TRAIN
# ============================================================

def get_live_train(
    train_number: str,
) -> dict[str, Any]:

    data = railradar_get(
        (
            f"/v1/trains/"
            f"{train_number.strip()}"
            f"/live"
        ),
        {
            "authoritative": "true",
            "haltsOnly": "true",
            "geometry": "true",
            "format": "geojson",
            "includeCoordinates": "true",
        },
    )

    if not isinstance(
        data,
        dict,
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "Unexpected RailRadar "
                "live response."
            ),
        )

    return data


# ============================================================
# ROUTE STOPS
# ============================================================

def get_route_stops(
    data: dict[str, Any],
) -> list[dict[str, Any]]:

    route = (
        data.get("route")
        or []
    )

    if not isinstance(
        route,
        list,
    ):
        return []

    stops: list[
        dict[str, Any]
    ] = []

    for station in route:

        if not isinstance(
            station,
            dict,
        ):
            continue

        halt = station.get(
            "isHalt"
        )

        is_halt = (
            halt is True
            or str(
                halt
            ).strip().lower()
            == "true"
        )

        if is_halt:
            stops.append(
                station
            )

    stops.sort(
        key=lambda item: (
            item.get("sequence")
            is None,
            item.get("sequence")
            or 0,
        )
    )

    return stops


# ============================================================
# CURRENT/NEXT STOP
# ============================================================

def get_stop_context(
    data: dict[str, Any],
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
]:

    stops = get_route_stops(
        data
    )

    if not stops:
        return (
            None,
            None,
        )

    status = normalize_status(
        data.get("status")
    )

    if is_not_started(status):
        return (
            None,
            stops[0],
        )

    current = (
        data.get(
            "currentLocation"
        )
        or {}
    )

    current_code = str(
        current.get(
            "stationCode"
        )
        or ""
    ).upper()

    current_sequence = (
        current.get(
            "sequence"
        )
    )

    current_index: int | None = None

    # First use station code.
    if current_code:

        for index, stop in enumerate(
            stops
        ):

            stop_code = str(
                stop.get(
                    "stationCode"
                )
                or ""
            ).upper()

            if (
                stop_code
                == current_code
            ):
                current_index = index
                break

    # Then sequence.
    if (
        current_index is None
        and current_sequence is not None
    ):

        for index, stop in enumerate(
            stops
        ):

            if (
                stop.get(
                    "sequence"
                )
                == current_sequence
            ):
                current_index = index
                break

    if current_index is not None:

        current_stop = stops[
            current_index
        ]

        current_status = normalize_status(
            current.get(
                "status"
            )
        )

        if current_status in {
            "approaching",
            "arriving",
            "upcoming",
        }:

            previous_stop = (
                stops[
                    current_index - 1
                ]
                if current_index > 0
                else None
            )

            return (
                previous_stop,
                current_stop,
            )

        next_stop = (
            stops[
                current_index + 1
            ]
            if (
                current_index + 1
                < len(stops)
            )
            else None
        )

        return (
            current_stop,
            next_stop,
        )

    # Train between stations.
    if current_sequence is not None:

        previous = [
            stop
            for stop in stops
            if (
                stop.get(
                    "sequence"
                ) is not None
                and stop.get(
                    "sequence"
                )
                < current_sequence
            )
        ]

        upcoming = [
            stop
            for stop in stops
            if (
                stop.get(
                    "sequence"
                ) is not None
                and stop.get(
                    "sequence"
                )
                > current_sequence
            )
        ]

        return (
            previous[-1]
            if previous
            else None,
            upcoming[0]
            if upcoming
            else None,
        )

    return (
        data.get(
            "previousHalt"
        )
        if isinstance(
            data.get(
                "previousHalt"
            ),
            dict,
        )
        else None,
        data.get(
            "nextHalt"
        )
        if isinstance(
            data.get(
                "nextHalt"
            ),
            dict,
        )
        else None,
    )


# ============================================================
# SPEED
# ============================================================

def get_current_speed(
    data: dict[str, Any],
) -> float | None:

    current = (
        data.get(
            "currentLocation"
        )
        or {}
    )

    return safe_number(
        first_value(
            current,
            [
                "speedKmh",
                "speed",
                "currentSpeed",
                "speedKmph",
            ],
        )
    )


def get_average_speed(
    data: dict[str, Any],
) -> float | None:

    train = (
        data.get("train")
        or {}
    )

    value = safe_number(
        first_value(
            train,
            [
                "avgSpeed",
                "averageSpeedKmh",
                "averageSpeed",
            ],
        )
    )

    if (
        value is not None
        and 0 < value < 250
    ):
        return value

    value = safe_number(
        first_value(
            data,
            [
                "avgSpeed",
                "averageSpeedKmh",
                "averageSpeed",
            ],
        )
    )

    if (
        value is not None
        and 0 < value < 250
    ):
        return value

    return None


# ============================================================
# COORDINATES
# ============================================================

def get_coordinates(
    data: dict[str, Any],
) -> tuple[
    float | None,
    float | None,
]:

    current = (
        data.get(
            "currentLocation"
        )
        or {}
    )

    lat = safe_number(
        first_value(
            current,
            [
                "lat",
                "latitude",
            ],
        )
    )

    lng = safe_number(
        first_value(
            current,
            [
                "lng",
                "longitude",
                "lon",
            ],
        )
    )

    if (
        lat is not None
        and lng is not None
    ):
        return (
            lat,
            lng,
        )

    current_code = str(
        current.get(
            "stationCode"
        )
        or ""
    ).upper()

    for stop in (
        data.get("route")
        or []
    ):

        stop_code = str(
            stop.get(
                "stationCode"
            )
            or ""
        ).upper()

        if (
            stop_code
            == current_code
        ):

            return (
                safe_number(
                    stop.get("lat")
                ),
                safe_number(
                    stop.get("lng")
                ),
            )

    return (
        None,
        None,
    )


# ============================================================
# LIVE RESPONSE
# ============================================================

def build_live_response(
    data: dict[str, Any],
) -> dict[str, Any]:

    train = (
        data.get("train")
        or {}
    )

    current = (
        data.get(
            "currentLocation"
        )
        or {}
    )

    previous, next_stop = (
        get_stop_context(
            data
        )
    )

    status = normalize_status(
        data.get("status")
    )

    delay = safe_number(
        data.get(
            "delayMinutes"
        )
    )

    if delay is None:
        delay = 0

    delay = max(
        0,
        delay,
    )

    current_distance = safe_number(
        first_value(
            current,
            [
                "distanceFromOriginKm",
                "distance",
            ],
        )
    )

    next_distance = (
        safe_number(
            next_stop.get(
                "distance"
            )
        )
        if next_stop
        else None
    )

    distance_to_next = None

    if (
        current_distance is not None
        and next_distance is not None
    ):

        distance_to_next = max(
            0,
            next_distance
            - current_distance,
        )

    current_code = (
        current.get(
            "stationCode"
        )
    )

    current_name = (
        current.get(
            "stationName"
        )
    )

    if (
        not current_name
        and current_code
    ):

        for stop in (
            data.get("route")
            or []
        ):

            if str(
                stop.get(
                    "stationCode"
                )
                or ""
            ).upper() == str(
                current_code
            ).upper():

                current_name = (
                    stop.get(
                        "stationName"
                    )
                )

                break

    lat, lng = get_coordinates(
        data
    )

    if is_not_started(status):

        status_text = (
            "Train has not started."
        )

    elif current_name:

        status_text = (
            f"Running near "
            f"{current_name}"
        )

    else:

        status_text = (
            status.replace(
                "-",
                " ",
            ).title()
            or "Status unavailable"
        )

    if is_not_started(status):

        last_stopped = "Not started"
        last_code = None

    else:

        last_stopped = (
            previous.get(
                "stationName"
            )
            if previous
            else None
        )

        last_code = (
            previous.get(
                "stationCode"
            )
            if previous
            else None
        )

    return {

        "train_number": (
            data.get(
                "trainNumber"
            )
            or train.get(
                "number"
            )
        ),

        "train_name": (
            data.get(
                "trainName"
            )
            or train.get(
                "name"
            )
        ),

        "status": status,

        "status_text": status_text,

        "is_live": bool(
            data.get(
                "isLive"
            )
        ),

        "tracking_mode": (
            data.get(
                "trackingMode"
            )
            or "real-time"
        ),

        "journey_date": (
            data.get(
                "startDate"
            )
            or today_ist()
        ),

        "last_update": (
            format_datetime(
                data.get(
                    "lastUpdatedAt"
                )
            )
            or data.get(
                "lastUpdatedAt"
            )
        ),

        "last_updated_at": (
            data.get(
                "lastUpdatedAt"
            )
        ),

        "delay": delay,

        "last_stopped_station": (
            last_stopped
        ),

        "last_stopped_station_code": (
            last_code
        ),

        "next_stopping_station": (
            next_stop.get(
                "stationName"
            )
            if next_stop
            else None
        ),

        "next_stopping_station_code": (
            next_stop.get(
                "stationCode"
            )
            if next_stop
            else None
        ),

        "next_stopping_distance_km": (
            next_distance
        ),

        "distance_to_next_stoppage_km": (
            distance_to_next
        ),

        "current_station": (
            current_name
        ),

        "current_station_code": (
            current_code
        ),

        "current_distance_km": (
            current_distance
        ),

        "current_speed_kmph": (
            get_current_speed(
                data
            )
        ),

        "average_speed_kmph": (
            get_average_speed(
                data
            )
        ),

        "avg_speed_kmph": (
            get_average_speed(
                data
            )
        ),

        "max_speed_kmph": safe_number(
            train.get(
                "maxSpeed"
            )
        ),

        "current_lat": lat,

        "current_lng": lng,

        "source": (
            train.get(
                "source"
            )
        ),

        "destination": (
            train.get(
                "destination"
            )
        ),

        "train_type": (
            train.get(
                "type"
            )
        ),

        "category": (
            train.get(
                "category"
            )
        ),

        "route": (
            data.get(
                "route"
            )
            or []
        ),

        "geometry": (
            data.get(
                "geometry"
            )
            or data.get(
                "geojson"
            )
        ),
    }


# ============================================================
# ETA / JOURNEY
# ============================================================

def build_eta(
    data: dict[str, Any],
) -> dict[str, Any]:

    train = (
        data.get("train")
        or {}
    )

    current = (
        data.get(
            "currentLocation"
        )
        or {}
    )

    status = normalize_status(
        data.get("status")
    )

    current_code = str(
        current.get(
            "stationCode"
        )
        or ""
    ).upper()

    current_sequence = (
        current.get(
            "sequence"
        )
    )

    delay = safe_number(
        data.get(
            "delayMinutes"
        )
    )

    if delay is None:
        delay = 0

    delay = max(
        0,
        delay,
    )

    stops = get_route_stops(
        data
    )

    predictions: list[
        dict[str, Any]
    ] = []

    current_index = -1

    # --------------------------------------------------------
    # FIND CURRENT STOP INDEX
    # --------------------------------------------------------

    for index, stop in enumerate(
        stops
    ):

        stop_code = str(
            stop.get(
                "stationCode"
            )
            or ""
        ).upper()

        if (
            current_code
            and stop_code
            == current_code
        ):

            current_index = index
            break

    if (
        current_index < 0
        and current_sequence is not None
    ):

        for index, stop in enumerate(
            stops
        ):

            if (
                stop.get(
                    "sequence"
                )
                == current_sequence
            ):

                current_index = index
                break

    # --------------------------------------------------------
    # EVERY STATION
    # --------------------------------------------------------

    for index, stop in enumerate(
        stops
    ):

        sequence = stop.get(
            "sequence"
        )

        code = str(
            stop.get(
                "stationCode"
            )
            or ""
        ).upper()

        stop_status = normalize_status(
            stop.get(
                "status"
            )
        )

        # ----------------------------------------------------
        # SCHEDULED
        # ----------------------------------------------------

        scheduled_arrival_raw = (
            first_value(
                stop,
                [
                    "scheduledArrival",
                    "sta",
                ],
            )
        )

        scheduled_departure_raw = (
            first_value(
                stop,
                [
                    "scheduledDeparture",
                    "std",
                ],
            )
        )

        # ----------------------------------------------------
        # RAW ACTUAL VALUES
        # ----------------------------------------------------
        #
        # IMPORTANT:
        # We preserve whatever real actual time
        # RailRadar returned.
        #
        # We do NOT erase it just because of sequence.

        actual_arrival_raw = (
            first_value(
                stop,
                [
                    "actualArrival",
                    "actual_arrival",
                    "actualArrivalTime",
                ],
            )
        )

        actual_departure_raw = (
            first_value(
                stop,
                [
                    "actualDeparture",
                    "actual_departure",
                    "actualDepartureTime",
                ],
            )
        )

        # ----------------------------------------------------
        # CURRENT
        # ----------------------------------------------------

        is_current = False

        if (
            current_code
            and code
            and code == current_code
        ):
            is_current = True

        if (
            not is_current
            and current_sequence is not None
            and sequence is not None
        ):
            is_current = (
                sequence
                == current_sequence
            )

        # ----------------------------------------------------
        # FUTURE
        # ----------------------------------------------------

        # Real actual values always win.
        if (
            actual_arrival_raw
            or actual_departure_raw
        ):

            is_future = False

        elif is_not_started(
            status
        ):

            is_future = True

        elif current_index >= 0:

            is_future = (
                index
                > current_index
            )

        elif (
            current_sequence is not None
            and sequence is not None
        ):

            is_future = (
                sequence
                > current_sequence
            )

        elif stop_status in {
            "upcoming",
            "approaching",
            "arriving",
        }:

            is_future = True

        else:

            is_future = False

        # ----------------------------------------------------
        # ETA
        # ----------------------------------------------------

        estimated_arrival_raw = None
        estimated_departure_raw = None

        if is_future:

            estimated_arrival_raw = (
                add_minutes(
                    scheduled_arrival_raw,
                    delay,
                )
            )

            estimated_departure_raw = (
                add_minutes(
                    scheduled_departure_raw,
                    delay,
                )
            )

        # ----------------------------------------------------
        # DISPLAY VALUES
        # ----------------------------------------------------

        actual_arrival = (
            format_time(
                actual_arrival_raw
            )
            if actual_arrival_raw
            else None
        )

        actual_departure = (
            format_time(
                actual_departure_raw
            )
            if actual_departure_raw
            else None
        )

        scheduled_arrival = (
            format_time(
                scheduled_arrival_raw
            )
        )

        scheduled_departure = (
            format_time(
                scheduled_departure_raw
            )
        )

        estimated_arrival = (
            format_time(
                estimated_arrival_raw
            )
            if estimated_arrival_raw
            else None
        )

        estimated_departure = (
            format_time(
                estimated_departure_raw
            )
            if estimated_departure_raw
            else None
        )

        # ----------------------------------------------------
        # COMPATIBILITY ARRIVAL
        # ----------------------------------------------------

        arrival = (
            actual_arrival
            or estimated_arrival
        )

        departure = (
            actual_departure
            or estimated_departure
        )

        # ----------------------------------------------------
        # DELAY
        # ----------------------------------------------------

        station_delay = safe_number(
            first_value(
                stop,
                [
                    "delayArrival",
                    "arrivalDelay",
                    "delay",
                ],
            )
        )

        if (
            station_delay is None
            and is_future
        ):

            station_delay = delay

        if (
            station_delay is not None
        ):

            station_delay = max(
                0,
                station_delay,
            )

        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        if is_current:

            state = "current"

        elif is_future:

            state = "upcoming"

        else:

            state = "passed"

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        predictions.append({

            "station": (
                stop.get(
                    "stationName"
                )
                or stop.get(
                    "name"
                )
                or code
            ),

            "code": (
                stop.get(
                    "stationCode"
                )
                or code
            ),

            "station_code": (
                stop.get(
                    "stationCode"
                )
                or code
            ),

            "sequence": sequence,

            "distance_km": safe_number(
                stop.get(
                    "distance"
                )
            ),

            # Scheduled
            "scheduled_arrival": (
                scheduled_arrival
            ),

            "scheduled_departure": (
                scheduled_departure
            ),

            # Actual
            "actual_arrival": (
                actual_arrival
            ),

            "actual_departure": (
                actual_departure
            ),

            # Original provider values
            "actual_arrival_iso": (
                actual_arrival_raw
            ),

            "actual_departure_iso": (
                actual_departure_raw
            ),

            # ETA
            "estimated_arrival": (
                estimated_arrival
            ),

            "estimated_departure": (
                estimated_departure
            ),

            # Existing frontend compatibility
            "arrival": arrival,

            "departure": departure,

            "platform": (
                stop.get(
                    "platform"
                )
                or stop.get(
                    "platformNumber"
                )
            ),

            "delay": station_delay,

            "state": state,

            "status": (
                stop.get(
                    "status"
                )
            ),

            "is_current": (
                is_current
            ),

            "is_halt": True,

            "lat": safe_number(
                stop.get(
                    "lat"
                )
            ),

            "lng": safe_number(
                stop.get(
                    "lng"
                )
            ),
        })

    previous, next_stop = (
        get_stop_context(
            data
        )
    )

    return {

        "train_number": (
            data.get(
                "trainNumber"
            )
            or train.get(
                "number"
            )
        ),

        "train_name": (
            data.get(
                "trainName"
            )
            or train.get(
                "name"
            )
        ),

        "journey_date": (
            data.get(
                "startDate"
            )
            or today_ist()
        ),

        "delay": delay,

        "last_update": (
            data.get(
                "lastUpdatedAt"
            )
        ),

        "current_station": (
            current.get(
                "stationName"
            )
        ),

        "current_station_code": (
            current.get(
                "stationCode"
            )
        ),

        "last_stopped_station": (
            previous.get(
                "stationName"
            )
            if previous
            else None
        ),

        "last_stopped_station_code": (
            previous.get(
                "stationCode"
            )
            if previous
            else None
        ),

        "next_stopping_station": (
            next_stop.get(
                "stationName"
            )
            if next_stop
            else None
        ),

        "next_stopping_station_code": (
            next_stop.get(
                "stationCode"
            )
            if next_stop
            else None
        ),

        "predictions": predictions,

        "stations": predictions,

        "eta": predictions,
    }


# ============================================================
# TRAIN BETWEEN STATIONS
# ============================================================

def normalize_train_summary(
    item: dict[str, Any],
    from_code: str,
    to_code: str,
) -> dict[str, Any]:

    train = (
        item.get(
            "train"
        )
        or {}
    )

    source = (
        item.get(
            "from"
        )
        or {}
    )

    destination = (
        item.get(
            "to"
        )
        or {}
    )

    return {

        "train_number": str(
            train.get(
                "number"
            )
            or item.get(
                "trainNumber"
            )
            or ""
        ),

        "train_name": (
            train.get(
                "name"
            )
            or item.get(
                "trainName"
            )
            or "Train"
        ),

        "from_station": (
            source.get(
                "name"
            )
            or from_code
        ),

        "to_station": (
            destination.get(
                "name"
            )
            or to_code
        ),

        "from_station_code": (
            source.get(
                "code"
            )
            or from_code
        ),

        "to_station_code": (
            destination.get(
                "code"
            )
            or to_code
        ),

        "departure_time": (
            source.get(
                "departure"
            )
        ),

        "arrival_time": (
            destination.get(
                "arrival"
            )
        ),

        "duration": (
            item.get(
                "duration"
            )
        ),

        "distance_km": (
            item.get(
                "distance"
            )
        ),

        "total_halts_between": (
            item.get(
                "totalHaltsBetween"
            )
        ),

        "days_of_run": (
            train.get(
                "runDays"
            )
            or []
        ),

        "type": (
            train.get(
                "type"
            )
        ),

        "category": (
            train.get(
                "category"
            )
        ),

        "live": (
            item.get(
                "live"
            )
            or {}
        ),
    }


# ============================================================
# BASIC
# ============================================================

@app.get("/")
def root():
    return {
        "name": APP_NAME,
        "status": "ok",
        "provider": "RailRadar",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": "RailRadar",
        "journey_date": today_ist(),
    }


# ============================================================
# STATION SEARCH
# ============================================================

@app.get("/stations/search")
def search_stations(
    q: str = Query(
        ...,
        min_length=1,
    ),
    limit: int = Query(
        10,
        ge=1,
        le=50,
    ),
):

    return railradar_get(
        "/v1/lookup/search/stations",
        {
            "q": q.strip(),
            "limit": limit,
        },
    )


# ============================================================
# TRAINS BETWEEN
# ============================================================

@app.get(
    "/trains/between/{from_station}/{to_station}"
)
def trains_between(
    from_station: str,
    to_station: str,
):

    from_code = (
        from_station
        .strip()
        .upper()
    )

    to_code = (
        to_station
        .strip()
        .upper()
    )

    data = railradar_get(
        (
            f"/v1/trains/between/"
            f"{from_code}/{to_code}"
        ),
        {
            "date": today_ist(),
            "live": "true",
        },
    )

    raw = (
        data.get(
            "trains"
        )
        if isinstance(
            data,
            dict,
        )
        else data
    )

    if not isinstance(
        raw,
        list,
    ):
        return []

    return [
        normalize_train_summary(
            item,
            from_code,
            to_code,
        )
        for item in raw
        if isinstance(
            item,
            dict,
        )
    ]


# ============================================================
# LIVE
# ============================================================

@app.get(
    "/train/{train_number}/live"
)
def train_live(
    train_number: str,
):

    data = get_live_train(
        train_number
    )

    return build_live_response(
        data
    )


# ============================================================
# TRAIN INFO
# ============================================================

@app.get(
    "/train/{train_number}"
)
def train_info(
    train_number: str,
):

    data = get_live_train(
        train_number
    )

    result = build_live_response(
        data
    )

    train = (
        data.get(
            "train"
        )
        or {}
    )

    result[
        "run_days"
    ] = (
        train.get(
            "runDays"
        )
        or []
    )

    result[
        "distance_km"
    ] = safe_number(
        train.get(
            "distance"
        )
    )

    result[
        "duration_minutes"
    ] = safe_number(
        train.get(
            "duration"
        )
    )

    result[
        "total_halts"
    ] = train.get(
        "totalHalts",
        0,
    )

    result[
        "coach_position"
    ] = train.get(
        "coachPosition"
    )

    return result


# ============================================================
# ETA
# ============================================================

@app.get(
    "/train/{train_number}/eta"
)
def train_eta(
    train_number: str,
):

    data = get_live_train(
        train_number
    )

    return build_eta(
        data
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.get(
    "/train/{train_number}/dashboard"
)
def train_dashboard(
    train_number: str,
):

    data = get_live_train(
        train_number
    )

    return {

        "live": (
            build_live_response(
                data
            )
        ),

        "eta": (
            build_eta(
                data
            )
        ),

        "train": (
            data.get(
                "train"
            )
            or {}
        ),

        "geometry": (
            data.get(
                "geometry"
            )
            or data.get(
                "geojson"
            )
        ),

        "route": (
            data.get(
                "route"
            )
            or []
        ),
    }


# ============================================================
# ROUTE
# ============================================================

@app.get(
    "/train/{train_number}/route"
)
def train_route(
    train_number: str,
):

    return railradar_get(
        (
            f"/v1/trains/"
            f"{train_number.strip()}"
            f"/route"
        ),
        {
            "format": "geojson",
            "stops": "true",
        },
    )


# ============================================================
# WEATHER
# ============================================================

@app.get("/weather")
def weather(
    lat: float = Query(
        ...,
        ge=-90,
        le=90,
    ),
    lng: float = Query(
        ...,
        ge=-180,
        le=180,
    ),
):

    try:

        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lng,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "apparent_temperature,"
                    "precipitation,"
                    "weather_code,"
                    "wind_speed_10m"
                ),
                "timezone": "Asia/Kolkata",
            },
            timeout=12,
        )

        response.raise_for_status()

        payload = response.json()

    except requests.RequestException as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Weather request failed: "
                f"{exc}"
            ),
        ) from exc

    return (
        payload.get(
            "current"
        )
        or {}
    )


# ============================================================
# ALL LIVE TRAINS
# ============================================================

@app.get("/live-map")
def live_map():

    return railradar_get(
        "/v1/legacy/trains/live-map"
    )