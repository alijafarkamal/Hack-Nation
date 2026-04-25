"""Referral: Twilio path + mock fallback (mocked)."""

from __future__ import annotations

import sys
import unittest.mock as mock

import pytest

sys.path.insert(0, ".")

from backend_api.schemas import ReferralPreviewRequest, ReferralSendRequest
from backend_api.services import referral_service as rs


def test_mock_when_no_twilio():
    with mock.patch("backend_api.services.referral_service.twilio_effective", return_value=False):
        p = rs.build_referral_preview(
            ReferralPreviewRequest(
                session_id="s1",
                to_facility="Test Hosp",
                to_phone="",
            ),
            "cid-1",
        )
        r = rs.send_referral(ReferralSendRequest(preview_id=p["preview_id"]), "cid-1")
        assert r["mode"] == "mock"
        assert r["success"] is True
        assert r.get("twilio_message_sid") is None


def test_twilio_path_mocked_sms():
    p = rs.build_referral_preview(
        ReferralPreviewRequest(
            session_id="s1",
            to_facility="H",
            to_phone="+919876543210",
        ),
        "cid-2",
    )
    with mock.patch("backend_api.services.referral_service.twilio_effective", return_value=True), mock.patch(
        "backend_api.services.referral_service._twilio_send_sms", return_value=("SM123", None)
    ):
        out = rs.send_referral(
            ReferralSendRequest(preview_id=p["preview_id"], to_phone="+919876543210"), "cid-2"
        )
        assert out["mode"] == "twilio"
        assert out["twilio_message_sid"] == "SM123"


def test_twilio_falls_back_on_sms_error():
    p = rs.build_referral_preview(
        ReferralPreviewRequest(session_id="s1", to_facility="H", to_phone="+919876543210"), "c"
    )
    with mock.patch("backend_api.services.referral_service.twilio_effective", return_value=True), mock.patch(
        "backend_api.services.referral_service._twilio_send_sms", return_value=(None, "rate limited")
    ):
        out = rs.send_referral(ReferralSendRequest(preview_id=p["preview_id"]), "c")
        assert out["mode"] == "mock_fallback"
        assert out["success"] is True
