# Profile-fetch logic adapted from toutatis (https://github.com/megadose/toutatis)
# by megadose, licensed under the GNU GPLv3. Adapted here to raise ProfileError
# with clear messages instead of returning {"error": ...} dicts, and to
# normalize the result into a Profile dataclass.

from __future__ import annotations

from dataclasses import dataclass
from json import decoder, dumps
from urllib.parse import quote_plus

import phonenumbers
import pycountry
import requests
from phonenumbers.phonenumberutil import region_code_for_country_code


@dataclass(frozen=True)
class Profile:
    username: str
    user_id: str
    full_name: str
    biography: str
    external_url: str | None
    is_business: bool
    business_category: str | None
    follower_count: int
    following_count: int
    public_email: str | None
    public_phone_number: str | None
    obfuscated_email: str | None
    obfuscated_phone: str | None
    profile_pic_url: str | None


def _format_public_phone(info: dict) -> str | None:
    """Mirrors toutatis's own formatting: "+<country code> <number> (Country)"."""
    number = info.get("public_phone_number")
    if not number:
        return None
    phone = f"+{info.get('public_phone_country_code', '')} {number}"
    try:
        parsed = phonenumbers.parse(phone)
        region = region_code_for_country_code(parsed.country_code)
        country = pycountry.countries.get(alpha_2=region)
        if country:
            phone += f" ({country.name})"
    except phonenumbers.NumberParseException:
        pass
    return phone


class ProfileError(RuntimeError):
    """Not found, rate-limited, or invalid session — human-readable message."""


def _get_user_id(username: str, session_id: str) -> str:
    headers = {"User-Agent": "iphone_ua", "x-ig-app-id": "936619743392459"}
    try:
        response = requests.get(
            f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
            headers=headers,
            cookies={"sessionid": session_id},
        )
    except requests.exceptions.RequestException as exc:
        raise ProfileError(f"request failed: {exc}") from exc

    if response.status_code == 404:
        raise ProfileError("profile not found")

    try:
        payload = response.json()
    except decoder.JSONDecodeError as exc:
        raise ProfileError("rate limited by Instagram — wait a few minutes and retry") from exc

    try:
        return payload["data"]["user"]["id"]
    except (KeyError, TypeError) as exc:
        # valid JSON, but not the expected shape — invalid/expired session,
        # login-required, or a rate-limit message instead of profile data
        message = payload.get("message") if isinstance(payload, dict) else None
        raise ProfileError(
            message or "invalid session or rate limited by Instagram — wait a few minutes and retry"
        ) from exc


def _get_user_info(user_id: str, session_id: str) -> dict:
    try:
        response = requests.get(
            f"https://i.instagram.com/api/v1/users/{user_id}/info/",
            headers={"User-Agent": "Instagram 64.0.0.14.96"},
            cookies={"sessionid": session_id},
        )
    except requests.exceptions.RequestException as exc:
        raise ProfileError(f"request failed: {exc}") from exc

    if response.status_code == 404:
        raise ProfileError("profile not found")
    if response.status_code == 429:
        raise ProfileError("rate limited by Instagram — wait a few minutes and retry")
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise ProfileError(f"request failed: {exc}") from exc

    try:
        payload = response.json()
    except decoder.JSONDecodeError as exc:
        raise ProfileError("rate limited by Instagram — wait a few minutes and retry") from exc

    info = payload.get("user") if isinstance(payload, dict) else None
    if not info:
        raise ProfileError("profile not found")
    return info


def _advanced_lookup(username: str) -> dict | None:
    """Obfuscated email/phone lookup. Returns None if unavailable — this
    step is not fatal to the overall profile fetch."""
    data = "signed_body=SIGNATURE." + quote_plus(
        dumps({"q": username, "skip_recovery": "1"}, separators=(",", ":"))
    )
    try:
        response = requests.post(
            "https://i.instagram.com/api/v1/users/lookup/",
            headers={
                "Accept-Language": "en-US",
                "User-Agent": "Instagram 101.0.0.15.120",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-IG-App-ID": "124024574287414",
                "Accept-Encoding": "gzip, deflate",
                "Host": "i.instagram.com",
                "Connection": "keep-alive",
                "Content-Length": str(len(data)),
            },
            data=data,
        )
        result = response.json()
    except (requests.exceptions.RequestException, decoder.JSONDecodeError):
        return None
    if not isinstance(result, dict) or "message" in result:
        return None
    return result


def get_profile(search: str, session_id: str, search_type: str = "username") -> Profile:
    """Fetch and normalize an Instagram profile. Raises ProfileError on failure."""
    if search_type == "username":
        user_id = _get_user_id(search, session_id)
        username = search
    else:
        try:
            user_id = str(int(search))
        except ValueError as exc:
            raise ProfileError("invalid id") from exc
        username = search  # resolved below from info["username"]

    info = _get_user_info(user_id, session_id)
    username = info.get("username", username)

    advanced = _advanced_lookup(username)
    obfuscated_email = advanced.get("obfuscated_email") if advanced else None
    obfuscated_phone = advanced.get("obfuscated_phone") if advanced else None

    return Profile(
        username=username,
        user_id=user_id,
        full_name=info.get("full_name", ""),
        biography=info.get("biography", "") or "",
        external_url=info.get("external_url") or None,
        is_business=bool(info.get("is_business")),
        business_category=info.get("category_name") or None,
        follower_count=int(info.get("follower_count") or 0),
        following_count=int(info.get("following_count") or 0),
        public_email=info.get("public_email") or None,
        public_phone_number=_format_public_phone(info),
        obfuscated_email=obfuscated_email or None,
        obfuscated_phone=obfuscated_phone or None,
        profile_pic_url=(info.get("hd_profile_pic_url_info") or {}).get("url"),
    )
