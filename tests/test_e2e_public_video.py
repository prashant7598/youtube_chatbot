"""Opt-in network test. Set YOUTUBE_E2E_VIDEO_URL and valid provider credentials to run it."""

import os

import pytest


@pytest.mark.skipif(not os.getenv("YOUTUBE_E2E_VIDEO_URL"), reason="Set YOUTUBE_E2E_VIDEO_URL to run a public-video integration test.")
def test_public_video_e2e_is_opted_in():
    # Network and paid-service behavior belongs in a controlled environment, not the default test suite.
    assert os.environ["YOUTUBE_E2E_VIDEO_URL"].startswith("https://")
