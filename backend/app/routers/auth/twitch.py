import random
import string
from typing import Optional
from urllib.parse import urlencode

import aiohttp
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.users import User

router = APIRouter()


def generate_random_string(length: int) -> str:
    """
    Generate a random alphanumeric string of the given length.

    :param length: Length of the generated string.
    :return: Randomly generated string.
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


async def fetch_user_info(access_token: str) -> Optional[dict | HTTPException]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": settings.TWITCH_CLIENT_ID
    }

    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.twitch.tv/helix/users", headers=headers) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="Failed to fetch user info")

            data = await response.json()

    if data and "data" in data and data["data"]:
        user = data["data"][0]

        user_data = {
            "id": user['id'],
            "username": user['login'],
            "display_name": user["display_name"],
            "avatar_url": user["profile_image_url"]
        }

        return user_data
    return

async def fetch_twitch_token(data: dict) -> dict:
    """
    Fetch an OAuth2 token from Twitch API.

    :param data: Dictionary containing OAuth2 token request parameters.
    :return: JSON response containing the token information.
    :raises HTTPException: If the request fails.
    """
    async with aiohttp.ClientSession() as session:
        async with session.post("https://id.twitch.tv/oauth2/token", data=data) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="Failed to fetch tokens")
            return await response.json()


@router.get("/login", summary="Initiate Twitch OAuth login")
async def twitch_login() -> RedirectResponse:
    """
    Redirects the user to the Twitch OAuth2 authorization URL.

    :return: RedirectResponse to the Twitch authorization page.
    """
    state = generate_random_string(16)

    query_params = {
        "response_type": "code",
        "client_id": settings.TWITCH_CLIENT_ID,
        "redirect_uri": settings.REDIRECT_URI,
        "state": state
    }
    response = RedirectResponse(url=f"https://id.twitch.tv/oauth2/authorize?{urlencode(query_params)}")

    response.set_cookie(
        key="twitch_state",
        value=state,
    )
    return response


@router.get("/callback", summary="Handle Twitch OAuth callback")
async def callback(request: Request, session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    """
    Handles the Twitch OAuth2 callback and exchanges the authorization code for an access token.

    :param request: FastAPI Request object.
    :param response: FastAPI Response object.
    :param session: AsyncSession dependency for database operations.
    :return: RedirectResponse to frontend with stored tokens.
    """

    if not request.query_params:
        raise HTTPException(status_code=400, detail="No query parameters received")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    stored_state = request.cookies.get("twitch_state")

    if not code or not state or state != stored_state:
        raise HTTPException(status_code=400, detail="Invalid or missing state")

    data = {
        "client_id": settings.TWITCH_CLIENT_ID,
        "client_secret": settings.TWITCH_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.REDIRECT_URI,
    }

    api_response = await fetch_twitch_token(data)
    access_token = api_response.get("access_token")
    refresh_token = api_response.get("refresh_token")

    user_info = await fetch_user_info(access_token)

    if user_info:

        statement = select(User).where(User.twitch_id == user_info['id'])
        result = await session.exec(statement)
        user_db = result.first()

        if not user_db:
            new_user = User(
                username=user_info['username'],
                avatar_url=user_info['avatar_url'],
                twitch_id=user_info['id'],
                twitch_display_name=user_info['display_name'],

                twitch_access_token=access_token,
                twitch_refresh_token=refresh_token
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)

    response = RedirectResponse(url=settings.FRONTEND_URL + "/configurator")
    response.delete_cookie("twitch_state")

    return response


@router.post("/refresh", summary="Refresh Twitch OAuth token")
async def refresh_token(refresh_token: str) -> dict:
    """
    Refreshes an expired Twitch OAuth2 access token using a refresh token.

    :param refresh_token: The refresh token obtained from a previous authentication.
    :return: JSON response containing the new access token.
    """
    data = {
        "client_id": settings.TWITCH_CLIENT_ID,
        "client_secret": settings.TWITCH_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    return await fetch_twitch_token(data)
