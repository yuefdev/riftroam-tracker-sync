import unittest
from unittest.mock import Mock, patch
from sync import SourceError, fetch_snapshot, run, tracker_data


def response(body, status=200):
    result = Mock(status_code=status, content=b"{}")
    result.json.return_value = body
    return result


class TrackerSourceTests(unittest.TestCase):
    def test_blocked_request_does_not_become_a_missing_profile(self):
        session = Mock()
        session.get.return_value = response({}, 403)
        with self.assertRaisesRegex(SourceError, "HTTP 403"):
            tracker_data(session, "profile/riot/test")

    def test_html_challenge_is_reported_without_response_contents(self):
        session = Mock()
        blocked = response({}, 403)
        blocked.headers = {"cf-mitigated": "challenge"}
        blocked.json.side_effect = ValueError("HTML challenge")
        session.get.return_value = blocked
        with self.assertRaisesRegex(SourceError, r"HTTP 403 \(access challenge\)"):
            tracker_data(session, "profile/riot/test")

    def test_explicit_private_response_does_not_request_history(self):
        session = Mock()
        session.get.return_value = response({"errors": [{"code": "CollectorResultStatus::Private"}]})
        snapshot = fetch_snapshot(session, {"region": "eu", "gameName": "Player", "tagLine": "TR1"})
        self.assertEqual(snapshot["reason"], "private")
        self.assertIsNone(snapshot["profile"])
        self.assertEqual(session.get.call_count, 1)

    def test_explicit_not_found_http_response_is_not_a_source_failure(self):
        session = Mock()
        session.get.return_value = response({"errors": [{"code": "CollectorResultStatus::NotFound"}]}, 404)
        self.assertEqual(tracker_data(session, "profile/riot/test"), (None, "notFound"))

    def test_explicit_private_http_response_is_not_an_access_challenge(self):
        session = Mock()
        session.get.return_value = response({"errors": [{"code": "CollectorResultStatus::Private"}]}, 403)
        self.assertEqual(tracker_data(session, "profile/riot/test"), (None, "private"))

    def test_partial_history_failure_keeps_profile_and_encoded_riot_id(self):
        session = Mock()
        profile = {"platformInfo": {"platformUserHandle": "Çelik Pilot#아이스"}}
        session.get.side_effect = [response({"data": profile}), response({}, 503)]
        snapshot = fetch_snapshot(session, {"region": "eu", "gameName": "Çelik Pilot", "tagLine": "아이스"})
        self.assertEqual(snapshot["profile"], profile)
        self.assertIsNone(snapshot["history"])
        self.assertIn("%C3%87elik%20Pilot%23%EC%95%84%EC%9D%B4%EC%8A%A4", session.get.call_args_list[0].args[0])


class HostedRefreshTests(unittest.TestCase):
    def test_saved_accounts_refresh_from_the_free_source_without_tracker_requests(self):
        account = {"region": "eu", "gameName": "Player", "tagLine": "TR1"}
        api = Mock()
        api.get.return_value = response({"accounts": [account], "next": None})
        api.post.return_value = response({"ok": True})
        with patch.dict("os.environ", {"PROFILE_SYNC_KEY": "test-key-" * 8}), patch("sync.requests.Session", return_value=api) as session:
            self.assertEqual(run(), 0)
        session.assert_called_once()
        submitted = api.post.call_args.kwargs["json"]
        self.assertEqual(submitted["source"], "opgg")
        self.assertEqual(submitted["account"], account)
        self.assertNotIn("profile", submitted)
        api.close.assert_called_once()

    def test_source_outages_fail_the_workflow_instead_of_reporting_success(self):
        api = Mock()
        api.get.return_value = response({"accounts": [{"region": "eu", "gameName": "Player", "tagLine": "TR1"}], "next": None})
        api.post.return_value = response({}, 500)
        with patch.dict("os.environ", {"PROFILE_SYNC_KEY": "test-key-" * 8}), patch("sync.requests.Session", return_value=api):
            self.assertEqual(run(), 1)


if __name__ == "__main__":
    unittest.main()
